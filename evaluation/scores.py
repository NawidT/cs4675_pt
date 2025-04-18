import pandas as pd
import re
import numpy as np
from rouge_score import rouge_scorer
from bert_score import score

# Load Excel file
df = pd.read_excel("data.xlsx")

# Cleanse function
def cleanse(text):
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)             # Normalize whitespace
    text = re.sub(r"[^\w\s]", "", text)          # Remove punctuation
    return text

gpt_responses_clean = df["GPT Response"].apply(cleanse).tolist()
human_responses_clean = df["Response"].apply(cleanse).tolist()

# ROUGE setup
scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
rouge1_p, rouge1_r, rouge1_f1 = [], [], []
rouge2_p, rouge2_r, rouge2_f1 = [], [], []
rougeL_p, rougeL_r, rougeL_f1 = [], [], []

# Compute ROUGE
for ref, pred in zip(human_responses_clean, gpt_responses_clean):
    scores = scorer.score(ref, pred)
    rouge1_p.append(scores["rouge1"].precision)
    rouge1_r.append(scores["rouge1"].recall)
    rouge1_f1.append(scores["rouge1"].fmeasure)

    rouge2_p.append(scores["rouge2"].precision)
    rouge2_r.append(scores["rouge2"].recall)
    rouge2_f1.append(scores["rouge2"].fmeasure)

    rougeL_p.append(scores["rougeL"].precision)
    rougeL_r.append(scores["rougeL"].recall)
    rougeL_f1.append(scores["rougeL"].fmeasure)

def compute_mean(scores):
    if isinstance(scores, list):
        return round(np.mean(scores), 4)
    return round(scores.mean().item(), 4)

print(f"\nROUGE-1: P = {compute_mean(rouge1_p)} R = {compute_mean(rouge1_r)} F1 = {compute_mean(rouge1_f1)}")
print(f"ROUGE-2: P = {compute_mean(rouge2_p)} R = {compute_mean(rouge2_r)} F1 = {compute_mean(rouge2_f1)}")
print(f"ROUGE-L: P = {compute_mean(rougeL_p)} R = {compute_mean(rougeL_r)} F1 = {compute_mean(rougeL_f1)}")

# Compute BERTScore
P, R, F1 = score(gpt_responses_clean, human_responses_clean, lang="en")

print("\nBERTScore:")
print(f"Precision: {compute_mean(P)}")
print(f"Recall   : {compute_mean(R)}")
print(f"F1       : {compute_mean(F1)}")
