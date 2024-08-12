from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation import GenerationConfig
from peft import AutoPeftModelForCausalLM


def qwen_eval_relevance(image_path, question, model, tokenizer):

    query_list = [{"image": image_path}]

    query_list.append({"text": question})

    query = tokenizer.from_list_format(query_list)
    output_prob = model.chat(
        tokenizer,
        query=query,
        history=None,
        return_dict_in_generate=True,
        output_scores=True,
        do_sample=False,
    )

    return output_prob


def qwen_chat(image_path, question, model, tokenizer):

    query_list = [{"image": image_path}]

    query_list.append({"text": question})

    query = tokenizer.from_list_format(query_list)
    response, _ = model.chat(tokenizer, query=query, history=None)

    return response


if __name__ == "__main__":
    model_path = "Qwen/Qwen-VL-Chat"
    adapter_path = (
        "../checkpoints/qwen-vl-chat-2epoch-4batch_size-webqa-reranker-caption-lora"
    )

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    mm_model = AutoPeftModelForCausalLM.from_pretrained(
        adapter_path,  # path to the output directory
        device_map="auto",
        trust_remote_code=True,
    ).eval()

    image_path = "../assets/framework.png"
    query = "Image Caption: Centennial Olympic Park splash fountain\nQuestion:\"Are there more than 6 tall lamp posts surrounding the fountain at Centennial Park?\"\nBased on the image and its caption, is the image relevant to the question? Answer 'Yes' or 'No'."
    # ans = qwen_chat(image_path, query, mm_model, tokenizer)
    ans = qwen_eval_relevance(image_path, query, mm_model, tokenizer)
    print(ans)