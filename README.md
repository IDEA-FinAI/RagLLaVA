# RagVL
This is the official repo for the paper: ["MLLM Is a Strong Reranker: Advancing Multimodal Retrieval-augmented Generation via Knowledge-enhanced Reranking and Noise-injected Training"](https://arxiv.org/pdf/2407.21439).

![image](https://github.com/IDEA-FinAI/RagVL/blob/main/assets/framework.png)

## Updates
- [2024-09-20]: To better reflect the generality of our proposed method, we rename it to **RagVL**.
- [2024-08-05]: Codes of RagVL (RagLLaVA) released.
- [2024-07-31]: Paper of RagVL (RagLLaVA) online.

## Getting Started
### Environment Setup
The required libraries for running RagVL can be found in `requirements.txt`. We recommend following [LLaVA](https://github.com/haotian-liu/LLaVA) to configure your environment.

### Data Preparation
Before running RagVL, please:

1. Download from [Google Drive](https://drive.google.com/drive/folders/1wY18Vbrb8yDbFSg1Te-FQIs84AYYh48Z?usp=drive_link) for **datasets** and **checkpoints**. 

2. Download from [WebQA](https://github.com/WebQnA/WebQA) and [MultimodalQA](https://github.com/allenai/multimodalqa) for **image files**.

3. Unzip the file. Place the `checkpoints/` and `datasets/` into `RagVL/`.

4. Place the `tasks/` into `RagVL/finetune/`.

5. Place the `MMQA_imgs/` and `train_img/` into `RagVL/finetune/tasks/`.

6. Place the `val_image/` into `RagVL/datasets/`.

## Training
1. Reranker

| Models | Global Batch Size | Epochs |
| --- | ---: | ---: | 
| LLaVA-v1.5-13B | 16 | 2 (WebQA) / 1 (others) |
| Qwen-VL-Chat | 16 | 2 (WebQA) / 1 (others) |
| mPLUG-Owl2 | 16 | 2 (WebQA) / 1 (others) |
| InternVL2-1B | 16 | 1 |
| InternVL2-2B | 16 | 1 |

2. Generator

| Models | Global Batch Size | Epochs |
| --- | ---: | ---: | 
| LLaVA-v1.5-13B | 16 | 2 (WebQA) / 3 (MMQA) |
| InternVL2-1B | 16 | 1 |
| InternVL2-2B | 16 | 1 |

Except for the above two hyperparameters, the others follow the default settings from different models.

To finetune LLaVA-v1.5-13B, Qwen-VL-Chat, and mPLUG-Owl2, find the corresponding finetune script in `RagVL/finetune/scripts/`.

To finetune InternVL2-1B and InternVL2-2B, find the corresponding finetune script in `RagVL/internvl_chat/shell/internvl2.0/2nd_finetune`.

## Evaluation
To evaluate RagVL on WebQA / MultimodalQA, you can employ the following command:

```
python webqa_pipeline.py \  # same arguments on mmqa_pipeline.py
--reranker_model caption_lora \ # select the reranker
--generator_model noise_injected_lora \ # select the generator
--filter 0 \ # select the adaptive threshold
--clip_topk 20 \ # we first retrieve 20 candidates by default
```

To evaluate the oracle settings on WebQA / MultimodalQA, you can employ the following command:

```
python webqa_oracle.py \  # same arguments on mmqa_oracle.py
```

## Citation
If you are interested or inspired by this work, you can cite us by:
```sh
@article{chen2024mllm,
  title={MLLM Is a Strong Reranker: Advancing Multimodal Retrieval-augmented Generation via Knowledge-enhanced Reranking and Noise-injected Training},
  author={Chen, Zhanpeng and Xu, Chengjin and Qi, Yiyan and Guo, Jian},
  journal={arXiv preprint arXiv:2407.21439},
  year={2024}
}
```

## Related Projects
- [LLaVA](https://github.com/haotian-liu/LLaVA): Large Language and Vision Assistant
- [Qwen-VL](https://github.com/QwenLM/Qwen-VL): A Versatile Vision-Language Model for Understanding, Localization, Text Reading, and Beyond
- [mPLUG-Owl](https://github.com/X-PLUG/mPLUG-Owl): The Powerful Multi-modal Large Language Model Family
- [InternVL](https://github.com/OpenGVLab/InternVL): A Pioneering Open-Source Alternative to GPT-4o
- [Visualized BGE](https://github.com/FlagOpen/FlagEmbedding/tree/master/FlagEmbedding/visual): A universal multi-modal embedding model
- [VCD](https://github.com/DAMO-NLP-SG/VCD): Mitigating Object Hallucinations in Large Vision-Language Models through Visual Contrastive Decoding
- [CAL](https://github.com/foundation-multimodal-models/CAL): Prioritizing Visual Correlation by Contrastive Alignment


