# YouBike Demand Prediction & Optimization

## 1. Project Overview

本專題目標為建立一套 **YouBike 站點需求預測與智慧調度系統**。

系統將使用臺北市 YouBike 開放資料、時間特徵與天氣資料，分析不同站點的使用情況，並建立 Machine Learning / Deep Learning 模型預測未來短時間內的租借需求與可用車輛變化。

在需求預測完成後，再加入最佳化模型，計算不同站點之間較合理的車輛調度方式。

本專題同時作為 AI / Data Science 研究所申請與實習作品集使用，因此重點不只是完成預測系統，也必須完整呈現：

- Data Collection
- Data Cleaning
- Exploratory Data Analysis
- Feature Engineering
- Machine Learning
- Deep Learning
- Model Evaluation
- Optimization
- Visualization
- Git / GitHub 專案管理

---

## 2. Research Question

主要研究問題：

> 是否能透過歷史 YouBike 使用資料、時間資訊與天氣資訊，預測特定站點未來的短期使用需求，並進一步利用最佳化方法改善站點間的車輛調度？

延伸問題：

1. 哪些因素最影響 YouBike 使用需求？
2. 不同 Machine Learning 模型的預測效果有何差異？
3. Deep Learning 是否能比傳統 Machine Learning 提供更好的時間序列預測？
4. 天氣資料加入後是否能改善模型表現？
5. 如何將預測結果轉換為實際的車輛調度建議？

---

## 3. Project Objectives

### Phase 1 — Data Analysis

- 收集 YouBike 官方 Open Data
- 整理與清理資料
- 分析不同站點的租借模式
- 分析尖峰與離峰時段
- 分析平日與假日差異
- 分析天氣與使用需求的關係

### Phase 2 — Machine Learning

建立基礎預測模型，例如：

- Linear Regression
- Random Forest
- XGBoost

預測目標可能包含：

- 未來 30 分鐘需求量
- 未來 60 分鐘需求量
- 未來可用車輛數量
- 是否即將發生缺車 / 滿站

### Phase 3 — Deep Learning

嘗試時間序列模型：

- LSTM
- GRU（選做）

並與傳統 Machine Learning 模型比較。

### Phase 4 — Optimization

將模型預測的各站需求轉換為最佳化問題。

例如：

- 哪些站需要補車？
- 哪些站有多餘車輛？
- 每個站應調入 / 調出幾輛？
- 如何降低調度距離與缺車成本？

可考慮：

- Linear Programming
- Mixed Integer Programming
- OR-Tools
- PuLP

### Phase 5 — Visualization / Demo

建立簡單 Dashboard 或視覺化成果，例如：

```text
捷運公館站

目前可借：12 輛

AI Prediction
30 分鐘後：7 輛
60 分鐘後：2 輛

⚠ High risk of bike shortage

Suggested Redistribution:
+6 bikes
```

---

## 4. Planned Data Sources

優先使用官方或公開資料來源。

### YouBike Data

可能使用：

- YouBike 2.0 即時站點資料
- YouBike 歷史借還紀錄
- 站點基本資訊
- 起訖站交易量

需要確認：

- Dataset 欄位
- 更新頻率
- 資料期間
- License
- 是否適合 Machine Learning

### Weather Data

可能使用中央氣象署 Open Data。

特徵可能包含：

- Temperature
- Rainfall
- Weather condition
- Humidity

---

## 5. Possible Features

模型輸入特徵可能包含：

### Time Features

- Hour
- Day of week
- Month
- Weekend
- Holiday
- Rush hour

### Station Features

- Station ID
- Location
- Capacity
- Previous available bikes

### Historical Features

- Previous 15-minute demand
- Previous 30-minute demand
- Previous 60-minute demand
- Moving average

### Weather Features

- Temperature
- Rainfall
- Humidity
- Weather condition

---

## 6. Machine Learning Workflow

完整流程：

```text
Raw Data
    ↓
Data Cleaning
    ↓
Exploratory Data Analysis
    ↓
Feature Engineering
    ↓
Train / Validation / Test Split
    ↓
Baseline Model
    ↓
Machine Learning Models
    ↓
Deep Learning Model
    ↓
Model Evaluation
    ↓
Error Analysis
    ↓
Demand Prediction
    ↓
Optimization
    ↓
Dashboard / Visualization
```

---

## 7. Model Evaluation

Regression 問題預計使用：

- MAE
- RMSE
- R²

如果建立缺車 / 滿站分類模型：

- Accuracy
- Precision
- Recall
- F1-score
- Confusion Matrix

避免只報告單一 Accuracy。

---

## 8. Planned Tech Stack

### Programming

- Python

### Data Processing

- Pandas
- NumPy

### Visualization

- Matplotlib

### Machine Learning

- scikit-learn
- XGBoost

### Deep Learning

後期加入：

- PyTorch

### Optimization

後期評估：

- OR-Tools
- PuLP

### Development

- Git
- GitHub
- Jupyter Notebook
- Codex

---

## 9. Repository Structure

```text
youbike-demand-prediction/
│
├── README.md
├── PROJECT_PLAN.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── raw/
│   └── processed/
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_feature_engineering.ipynb
│   ├── 04_machine_learning.ipynb
│   └── 05_model_evaluation.ipynb
│
├── src/
│
├── models/
│
├── results/
│
└── images/
```

資料夾用途：

### data/raw

保存原始資料。

原則：

> 不直接修改原始資料。

### data/processed

保存經過清理與轉換後的資料。

### notebooks

保存資料分析與模型實驗 Notebook。

### src

正式 Python 程式碼。

未來可以包含：

```text
data_loader.py
preprocessing.py
features.py
train.py
predict.py
optimization.py
```

### models

保存訓練完成的模型。

### results

保存：

- evaluation results
- CSV
- experiment results

### images

保存：

- EDA charts
- model evaluation charts
- architecture diagrams
- README images

---

## 10. GitHub Rules

### Commit 原則

每完成一個有意義的小階段就 Commit。

例如：

```text
Initialize project structure

Add YouBike data loader

Add exploratory data analysis

Add weather data integration

Train baseline model

Add XGBoost model

Add model evaluation

Add optimization model
```

避免使用：

```text
update
fix
test
123
final
```

作為主要 Commit message。

---

## 11. Security Rules

禁止將以下內容 Push 到 GitHub：

- API Key
- Access Token
- Password
- Secret
- Private credential
- .env

`.gitignore` 至少加入：

```text
.env
.venv/
__pycache__/
.DS_Store
.ipynb_checkpoints/
```

---

## 12. README Requirements

README 最終至少需要包含：

1. Project Overview
2. Problem
3. Research Question
4. Dataset
5. System Architecture
6. Data Analysis
7. Models
8. Evaluation
9. Results
10. Optimization
11. Demo
12. Tech Stack
13. Project Structure
14. Future Work

禁止在模型尚未完成之前填寫假的：

- Accuracy
- RMSE
- F1-score
- Prediction Result

尚未完成的部分標示：

> 🚧 In Development

---

## 13. First Development Milestone

目前先不要開始 Deep Learning 或 Optimization。

第一階段只完成以下內容：

### Milestone 1

- [x] 建立 Repository 基礎架構
- [x] 建立 README.md
- [x] 建立 PROJECT_PLAN.md
- [x] 建立 requirements.txt
- [x] 建立 .gitignore
- [x] 找到官方 YouBike Dataset
- [x] 確認 Dataset 欄位
- [x] 下載一小部分資料進行測試
- [x] 建立 `01_data_exploration.ipynb`
- [x] 使用 Pandas 載入資料
- [x] 顯示資料前 5 筆
- [x] 檢查資料 Shape
- [x] 檢查 Columns
- [x] 檢查 Missing Values
- [x] 基本 Descriptive Statistics
- [x] 建立第一張資料視覺化圖表

完成 Milestone 1 後才進入資料清理。

---

## 14. Instructions for Codex

在修改此 Repository 前，請先閱讀：

`PROJECT_PLAN.md`

所有程式與檔案修改應遵循此文件。

### Current Priority

目前只處理：

> Historical Data Integration + Extended EDA + Feature Engineering

請不要提前：

- 建立 LSTM
- 建立 PyTorch Model
- 建立 Optimization
- 宣稱模型已有成果
- 填寫假的 Evaluation Metrics

### When Writing Code

請：

1. 保持程式易讀。
2. 避免過度複雜設計。
3. 為重要程式加入簡短註解。
4. 不要硬編 Dataset 欄位。
5. 若 Dataset 格式尚未確認，先檢查資料。
6. 不要把 API Key 寫入原始碼。
7. 優先建立容易理解的版本，再逐步改善。

### After Every Task

完成任務後請說明：

1. 新增哪些檔案
2. 修改哪些檔案
3. 每個修改的用途
4. 下一步建議
5. 是否有任何需要使用者決定的事項

---

## 15. Project Status

🚧 **In Development**

Completed Stage:

> Milestone 1 — Project Setup, Data Collection & Initial Exploration
>
> Milestone 2 — Reproducible Data Collection & Cleaning Pipeline
>
> Stage 3 Tooling — Historical Collection & Feature Engineering Foundation
>
> Stage 4 — Official Historical Transfer-Demand Integration
>
> Stage 5 — Full-year Historical Demand + Weather Integration

Current Stage:

> Baseline Model Readiness + Historical Snapshot Accumulation

### Milestone 2 Deliverables

- [x] 建立可重複執行的官方 API 快照蒐集器
- [x] 驗證 JSON 結構與必要欄位
- [x] 建立多快照載入與合併流程
- [x] 統一欄位名稱、資料型別與臺北時區
- [x] 檢查負數、經緯度、重複列與容量一致性
- [x] 保留不可用車柱與站點資料延遲資訊
- [x] 建立跨快照車輛淨變化特徵
- [x] 產生資料品質與快照摘要報告
- [x] 建立並執行 `02_data_cleaning.ipynb`
- [x] 建立資料管線自動化測試
- [x] 撰寫 Stage 2 中文說明文件

Next Stage:

> Time-aware Hourly Baseline Model

### Stage 3 Deliverables

- [x] 建立固定間隔與指定份數的歷史快照蒐集器
- [ ] 累積至少 7 天且包含平日與週末的真實快照
- [x] 建立 hour、weekday、month、weekend、rush hour 特徵
- [x] 建立週期性 sine / cosine 時間特徵
- [x] 建立 15／30／60 分鐘 backward-only lag 特徵
- [x] 建立排除當前列的 30／60 分鐘 rolling 特徵
- [x] 建立獨立的 30／60 分鐘 future target 欄位
- [x] 建立 feature coverage 報告
- [x] 建立並執行 `03_feature_engineering.ipynb`
- [x] 建立 future leakage 防護測試
- [x] 撰寫 Stage 3 中文說明文件

### Model Readiness

兩份公開固定樣本的 30／60 分鐘 future target coverage 為 0%；本機一小時蒐集測試已使 30 分鐘 coverage 達 42.16%，但 60 分鐘仍為 0%。目前資料期間仍不足，因此尚未進入模型訓練。待多日歷史資料累積且完成擴充 EDA 後，才建立 Baseline Model。

### Stage 4 Deliverables

- [x] 確認官方 2023 轉乘 YouBike 歷史資料來源與授權
- [x] 下載並稽核 2023 年 1 月 593,616 筆資料
- [x] 確認借還時間為 hourly granularity
- [x] 建立大型歷史 CSV 串流下載器與來源 registry
- [x] 建立歷史交易欄位驗證與清理管線
- [x] 保留並揭露無法安全刪除的相同交易列
- [x] 建立歷史站名正規化與現行站點對應檢查
- [x] 建立 station-hour 借還需求聚合
- [x] 建立 daily、hourly、top-station 與 quality reports
- [x] 建立並執行 `04_historical_demand_analysis.ipynb`
- [x] 撰寫 Stage 4 中文說明文件

### Historical Dataset Scope

2023 歷史資料僅涵蓋公車／捷運轉乘 YouBike 的租借紀錄，不代表所有 YouBike 使用者。此資料用於 hourly historical demand；自行蒐集的即時快照持續用於 30／60 分鐘 station availability 預測，兩者不可混為同一 target。

### Stage 5 Deliverables

- [x] 註冊並下載 2023 全年 12 個官方歷史月份
- [x] 建立逐月處理、全年合併的記憶體友善管線
- [x] 稽核全年 7,388,479 筆轉乘相關旅次
- [x] 揭露 7 個缺漏站名並保留每筆仍可使用的借／還事件
- [x] 建立 4,670,320 筆 station-hour demand 資料
- [x] 建立全年 monthly、daily、hourly、station 與 quality reports
- [x] 下載並清理 2023 全年 8,760 小時歷史天氣
- [x] 建立需求與天氣 many-to-one 同小時合併，匹配率 100%
- [x] 建立雨天／非雨天分層比較，避免直接混合平假日與小時
- [x] 建立並執行 `05_weather_integration.ipynb`
- [x] 撰寫 Stage 5 中文說明文件

### Weather Dataset Scope

目前天氣使用 Open-Meteo Historical Weather API 的臺北單一參考點歷史再分析資料，以確保流程不依賴寫入原始碼的 API Key 且可重現。此資料不是每個 YouBike 站點的現地氣象站觀測；中央氣象署資料留待後續作實測驗證。雨天與需求差異目前僅為描述性關聯，不宣稱因果效果。
