import faiss
import numpy as np
import clip
import torch
import ipdb
import json
from tqdm import tqdm
from utils.metrics import webqa_metrics_approx
from utils.indexing_faiss import text_to_image

import argparse

from llava.model.builder import load_pretrained_model
from llava.mm_utils import get_model_name_from_path
from llava.eval.run_llava import llava_chat, eval_relevance


def cal_relevance(model_path, image_path, question, model, tokenizer, image_processor):

    args = type(
        "Args",
        (),
        {
            "model_path": model_path,
            "model_base": None,
            "model_name": get_model_name_from_path(model_path),
            "query": question,
            "conv_mode": None,
            "image_file": image_path,
            "sep": ",",
            "temperature": 0,
            "top_p": None,
            "num_beams": 1,
            "max_new_tokens": 512,
        },
    )()

    prob = eval_relevance(args, tokenizer, model, image_processor)

    return prob


def infer(
    model_path, image_file, question, model, tokenizer, image_processor, from_array=True
):
    if "webqa" in model_path:
        prompt_template = question
    else:
        prompt_template = f"""Question: {question}\nAnswer the question with less than eight words based on the provided images."""

    args = type(
        "Args",
        (),
        {
            "model_path": model_path,
            "model_base": None,
            "model_name": get_model_name_from_path(model_path),
            "query": prompt_template,
            "conv_mode": None,
            "image_file": image_file,
            "sep": ",",
            "temperature": 0,
            "top_p": None,
            "num_beams": 1,
            "max_new_tokens": 512,
        },
    )()

    output = llava_chat(args, tokenizer, model, image_processor, from_array=from_array)

    return output


# ------------- CLIP + Rerank -------------


def clip_rerank_generate(
    val_dataset,
    ind,
    index_to_image_id,
    model_path,
    generator_path,
    mm_model,
    clip_model,
    tokenizer,
    image_processor,
    generator_model,
    save_path,
    filter,
    mode,
    rerank_off,
    use_caption,
    topk=20,
):
    retrieval_correct = 0
    retrieval_num = 0
    retrieval_pos_num = 0
    acc_scores = {"ALL": [], "Single": [], "Multi": []}

    hard_examples = {}
    probabilities = {"gt": [], "false": []}
    if use_caption:
        if mode == "val":
            with open("WebQA_vanilla_caption_val_image.json", "r") as f:
                captions = json.load(f)
        elif mode == "dev" or mode == "train":
            with open("WebQA_vanilla_caption_train_dev_image.json", "r") as f:
                captions = json.load(f)

    with open(save_path, "w") as f:
        f.write("{\n")
        for guid in tqdm(val_dataset):
            datum = val_dataset[guid]
            question = datum["Q"]
            em_answer = datum["EM"]
            pos_imgs = datum["img_posFacts"]
            qcate = datum["Qcate"]

            pos_source = []
            retrieved_imgs = []
            rerank_imgs = {}

            for item in pos_imgs:
                pos_source.append(str(item["image_id"]))
            D, I = text_to_image(question, clip_model, ind, topk)
            for d, j in zip(D[0], I[0]):
                img_id = index_to_image_id[str(j)]
                retrieved_imgs.append(str(img_id))

            if not rerank_off:
                for id in retrieved_imgs:
                    if mode == "val":
                        img_path = "val_image/" + id + ".png"
                    elif mode == "dev" or mode == "train":
                        img_path = "playground/data/train_img/" + id + ".png"

                    if use_caption:
                        query = (
                            "Image Caption: "
                            + captions[id]
                            + "\nQuestion: "
                            + question
                            + "\nBased on the image and its caption, is the image relevant to the question? Answer 'Yes' or 'No'."
                        )
                    else:
                        query = (
                            "Question: "
                            + question
                            + "\nIs this image relevant to the question? Answer 'Yes' or 'No'."
                        )

                    prob_yes = cal_relevance(
                        model_path,
                        img_path,
                        query,
                        mm_model,
                        tokenizer,
                        image_processor,
                    )
                    rerank_imgs[id] = float(prob_yes)

                top_sorted_imgs = dict(
                    sorted(rerank_imgs.items(), key=lambda item: item[1], reverse=True)[
                        :2
                    ]
                )

                intersect = set(pos_source).intersection(set(top_sorted_imgs.keys()))
                remaining = set(top_sorted_imgs.keys()).difference(intersect)

                for key in intersect:
                    probabilities["gt"].append(top_sorted_imgs[key])

                for key in remaining:
                    probabilities["false"].append(top_sorted_imgs[key])

                filtered_imgs = [
                    key for key, val in top_sorted_imgs.items() if val >= filter
                ]
            else:
                top_sorted_imgs = retrieved_imgs
                filtered_imgs = retrieved_imgs
                intersect = set(pos_source).intersection(set(retrieved_imgs))
                remaining = set(top_sorted_imgs).difference(intersect)

            if len(intersect) == 0:
                hard_examples[guid] = datum

            IMAGE_PATH = ""
            for i in range(len(filtered_imgs)):
                if mode == "val":
                    IMAGE_PATH += "val_image/" + filtered_imgs[i] + ".png"
                elif mode == "dev":
                    IMAGE_PATH += (
                        "playground/data/train_img/" + filtered_imgs[i] + ".png"
                    )
                if i != len(filtered_imgs) - 1:
                    IMAGE_PATH += ","

            output = infer(
                generator_path,
                IMAGE_PATH,
                question,
                generator_model,
                tokenizer,
                image_processor,
                from_array=False,
            )

            accuracy = webqa_metrics_approx(output, em_answer, qcate)
            acc_scores["ALL"].append(accuracy)

            if len(pos_imgs) == 1:
                acc_scores["Single"].append(accuracy)
            elif len(pos_imgs) > 1:
                acc_scores["Multi"].append(accuracy)

            retrieval_num += len(filtered_imgs)
            retrieval_pos_num += len(pos_source)
            retrieval_correct += len(set(pos_source).intersection(set(filtered_imgs)))

            output_json = {
                "question": question,
                "generator_answer": output,
                "em_answer": em_answer,
                "gt_images": pos_source,
                "retrieved_images": top_sorted_imgs,
            }
            new_data = json.dumps({guid: output_json})[1:-1]
            f.write(f"    {new_data},\n")  # 写入缩进的键值对

        f.write("}")

    # with open("webqa_distribution_prob_" + mode + ".json", "w") as json_file:
    #     json.dump(probabilities, json_file, indent=4)

    pre = retrieval_correct / retrieval_num
    recall = retrieval_correct / retrieval_pos_num
    f1 = 2 * pre * recall / (pre + recall)

    print("Retrieval pre:", pre)
    print("Retrieval recall:", recall)
    print("Retrieval F1:", f1)

    print("Generation ACC:", np.mean(acc_scores["ALL"]))
    print("Single Img ACC:", np.mean(acc_scores["Single"]))
    print("Multi Imgs ACC:", np.mean(acc_scores["Multi"]))

    print("Hard examples count:", len(hard_examples))
    return hard_examples


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reranker_model", type=str, default="lora_caption")
    parser.add_argument("--generator_model", type=str, default="base_sft")
    parser.add_argument("--datasets", type=str, default="val")
    parser.add_argument("--filter", type=float, default=0)
    parser.add_argument("--rerank_off", default=False, action="store_true")
    parser.add_argument("--clip_topk", type=int, default=20)

    args = parser.parse_args()
    print(args)

    save_path = (
        "_".join(
            [
                attr
                for attr in [
                    "answer_set",
                    args.generator_model,
                    str(args.filter)[2:],
                    "clip_top" + str(args.clip_topk) if args.clip_topk != 20 else "",
                ]
                if attr != ""
            ]
        )
        + ".json"
    )

    clip_model, preprocess = clip.load("ViT-L/14@336px", device="cuda", jit=False)

    ################### reranker_model ###################

    if args.reranker_model == "lora":
        model_path = "checkpoints/web/llava-v1.5-13b-task-lora-1"
        tokenizer, mm_model, image_processor, _ = load_pretrained_model(
            model_path=model_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(model_path),
        )

    elif args.reranker_model == "base":
        model_path = "liuhaotian/llava-v1.5-13b"
        tokenizer, mm_model, image_processor, _ = load_pretrained_model(
            model_path=model_path,
            model_base=None,
            model_name=get_model_name_from_path(model_path),
        )
    elif args.reranker_model == "lora_caption":
        model_path = "checkpoints/web/llava-v1.5-13b-2epoch-reranker-lora-caption"
        tokenizer, mm_model, image_processor, _ = load_pretrained_model(
            model_path=model_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(model_path),
        )
    elif args.reranker_model == "blend_lora_caption":
        model_path = "checkpoints/web/llava-v1.5-13b-2epoch-8batch_size-webqa-blend-long-answer-lora-caption"
        tokenizer, mm_model, image_processor, _ = load_pretrained_model(
            model_path=model_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(model_path),
        )

    ################### generator_model ###################

    if args.generator_model == "base":
        generator_path = "liuhaotian/llava-v1.5-13b"
        _, generator_model, _, _ = load_pretrained_model(
            model_path=generator_path,
            model_base=None,
            model_name=get_model_name_from_path(generator_path),
        )
    elif args.generator_model == "base_sft":
        generator_path = "checkpoints/web/llava-v1.5-13b-2epoch-webqa-lora"
        _, generator_model, _, _ = load_pretrained_model(
            model_path=generator_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(generator_path),
        )
    elif args.generator_model == "blend_sft":
        generator_path = model_path
        generator_model = mm_model

    elif args.generator_model == "dino_sft":
        generator_path = "checkpoints/web/llava-v1.5-13b-dino-webqa-lora"
        _, generator_model, _, _ = load_pretrained_model(
            model_path=generator_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(generator_path),
        )

    elif args.generator_model == "long_sft":

        # generator_path = (
        #     "checkpoints/web/llava-v1.5-13b-2epoch-8batch_size-webqa-long-answer-lora"
        # )
        generator_path = "checkpoints/web/llava-v1.5-13b-2epoch-8batch_size-webqa-long-answer-lora-all-ground-truth"
        _, generator_model, _, _ = load_pretrained_model(
            model_path=generator_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(generator_path),
        )

    elif args.generator_model == "long_distortion_sft":
        # generator_path = "checkpoints/web/llava-v1.5-13b-2epoch-8batch_size-webqa-long-answer-contrastive-distortion-lora-all-ground-truth"
        generator_path = "checkpoints/web/llava-v1.5-13b-2epoch-8batch_size-webqa-long-answer-contrastive-distortion-lora"
        _, generator_model, _, _ = load_pretrained_model(
            model_path=generator_path,
            model_base="liuhaotian/llava-v1.5-13b",
            model_name=get_model_name_from_path(generator_path),
        )

    if args.datasets == "val":
        with open("WebQA_val_image_objects.json", "r") as f:
            val_dataset = json.load(f)

        with open("WebQA_val_index_to_id.json", "r") as f:
            index_to_image_id = json.load(f)

        index = faiss.read_index("WebQA_val_image_large.index")

    elif args.datasets == "dev":
        with open("WebQA_dev_image.json", "r") as f:
            val_dataset = json.load(f)

        with open("WebQA_dev_index_to_id.json", "r") as f:
            index_to_image_id = json.load(f)

        index = faiss.read_index("WebQA_dev_image_large.index")

    elif args.datasets == "train":
        with open("WebQA_train_image.json", "r") as f:
            val_dataset = json.load(f)

        with open("WebQA_train_index_to_id.json", "r") as f:
            index_to_image_id = json.load(f)

        index = faiss.read_index("WebQA_train_image_large.index")

    with torch.no_grad():
        clip_rerank_generate(
            val_dataset,
            index,
            index_to_image_id,
            model_path,
            generator_path,
            mm_model,
            clip_model,
            tokenizer,
            image_processor,
            generator_model,
            save_path,
            filter=args.filter,
            mode=args.datasets,
            rerank_off=args.rerank_off,
            use_caption=True if "caption" in args.reranker_model else False,
            topk=args.clip_topk,
        )