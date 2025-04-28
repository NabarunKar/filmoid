# Plot-Based Movie Question Answering (Q&A)

This notebook implements a system that answers user questions about movie plots.  
It uses plot summaries and a transformer-based Question Answering (QA) model to retrieve and predict answers from the movie plots.

---

## Overview

The goal of this module is to:

- Retrieve the most relevant plot summaries based on a user's question.
- Use a transformer QA model to extract precise answers from the retrieved plots.
- Provide a direct answer based on the user's natural language query.

This extends the traditional movie recommendation system into an interactive, plot-aware conversational assistant.

---

## Files and Dependencies

| File                | Description                                    |
|---------------------|------------------------------------------------|
| `q_a_Plot.ipynb`     | Jupyter notebook for plot-based Q&A system     |
| `movies_with_plots.csv` | (Expected) CSV containing movie titles and plot summaries |
| `models/qa_model/`   | Pretrained QA model directory (such as a fine-tuned BERT) |

### Python Libraries Required

```bash
pip install pandas numpy transformers torch scikit-learn
```

---

## Workflow

### 1. Load Movie Plots Dataset

- A CSV file (`movies_with_plots.csv`) containing:
  - `movie_title`
  - `plot_summary`

This dataset acts as the context knowledge base.

### 2. Question Encoding

- User inputs a **natural language question**.
- Optionally, a specific movie title can be selected to narrow down the context.

### 3. Plot Retrieval (Optional)

- If no specific movie is selected, the system ranks plots by their relevance to the question.
- **TF-IDF vectorization** is used to score and retrieve the top-k relevant plots.

### 4. Question Answering Model

- A **Transformer QA model** (such as BERT fine-tuned on SQuAD) predicts answers.
- The model receives `(question, context)` pairs.
- Outputs:
  - Predicted answer span from the plot
  - Confidence scores

### 5. Return Best Answer

- The best answer (based on confidence or ranking) is returned to the user.

---

## Main Components

### Plot Retrieval
- `TfidfVectorizer` is used to embed both the question and plots.
- Cosine similarity identifies which plots are the most relevant to the input question.

### Question Answering
- A HuggingFace QA model (`AutoModelForQuestionAnswering`, `AutoTokenizer`) is loaded.
- For each plot, the system feeds the question and context into the model.
- The highest scoring answer is chosen.

---

## Model Assumptions

- The transformer model expects a relatively short input (< 512 tokens). Long plots are truncated if needed.
- If no high-confidence answer is found, the system may return "No good answer found" or similar.

---


## Acknowledgements

- [HuggingFace Transformers](https://huggingface.co/transformers/)
- [MovieLens Dataset](https://grouplens.org/datasets/movielens/)

