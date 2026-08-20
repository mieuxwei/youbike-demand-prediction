# Stage 2 說明：YouBike 資料蒐集與清理管線

## 1. 本階段完成了什麼

本階段把「手動下載一份 JSON」提升為可重複執行的資料工程流程：

```text
臺北市官方 YouBike API
        ↓
時間戳記原始快照（raw）
        ↓
結構與必要欄位驗證
        ↓
欄位重新命名、型別轉換、品質檢查
        ↓
相鄰快照淨變化特徵
        ↓
清理後 CSV + 品質報告
```

原始 JSON 不會被直接修改。所有清理結果都由程式重新產生，方便追蹤問題與重現分析。

## 2. 主要檔案

| 檔案 | 用途 |
|---|---|
| `src/collect_youbike.py` | 從官方 API 下載一份帶時間戳記的快照 |
| `src/data_pipeline.py` | 載入、驗證、清理、建立衍生欄位與摘要 |
| `src/prepare_data.py` | 串起完整 raw-to-processed 流程 |
| `notebooks/02_data_cleaning.ipynb` | 以 Notebook 展示清理流程與圖表 |
| `tests/test_data_pipeline.py` | 驗證欄位缺漏、清理規則與跨快照變化計算 |
| `results/data_quality_summary.csv` | 整體資料品質摘要 |
| `results/snapshot_summary.csv` | 每個快照的系統層級摘要 |

`data/processed/youbike_snapshots.csv` 是可重新產生的中間資料，因此不加入 Git。持續蒐集產生的 `data/raw/snapshots/*.json` 也不加入 Git，避免儲存庫隨時間快速增大。Repository 只保留兩份固定樣本，讓清理流程與測試結果可以重現。

## 3. 官方欄位如何轉換

| 官方欄位 | 清理後欄位 | 意義 |
|---|---|---|
| `srcUpdateTime` | `snapshot_time` | 整份 API 快照發布時間 |
| `mday` | `station_updated_at` | 個別站點資料更新時間 |
| `sno` | `station_id` | 站點代號 |
| `sna` | `station_name` | 站點名稱 |
| `sarea` | `district` | 行政區 |
| `ar` | `address` | 地址 |
| `Quantity` | `capacity` | 場站總停車格數 |
| `available_rent_bikes` | `available_bikes` | 可借車數 |
| `available_return_bikes` | `available_return_spaces` | 可還空位數 |
| `act` | `is_active` | 站點是否營運 |

時間欄位會解析成 `Asia/Taipei` 時區，數量與經緯度會轉成數值。必要欄位缺漏、負數、無效時間或不合理經緯度都會讓流程明確失敗，不會悄悄產生錯誤資料。

## 4. 重要清理決策

### 不可用車柱

實際資料中，部分站點符合：

```text
capacity > available_bikes + available_return_spaces
```

差值可能代表停用、保留或暫時不可使用的車柱。本專案將差值保存為：

```text
unavailable_docks = capacity - available_bikes - available_return_spaces
```

不能把差值直接補到可借車數或可還空位，否則會扭曲官方當下狀態。

### 車輛淨變化不是租借需求

相鄰快照的可借車數差異定義為：

```text
bike_net_change = current_available_bikes - previous_available_bikes
estimated_net_outflow = -bike_net_change
```

只有前後兩個快照都處於營運狀態且時間順序正確時才計算。

這個變化可能同時包含租車、還車、人工調度與資料修正，所以目前只能稱為「淨變化代理值」，不能稱為真實租借筆數。若要建立可靠的需求標籤，後續需累積更密集的歷史快照，並評估調度造成的干擾。

## 5. 目前可重現的資料品質結果

執行日期：2026-08-20（Asia/Taipei）。

| 指標 | 結果 |
|---|---:|
| 固定樣本快照 | 2 |
| 原始資料列 | 3,580 |
| 清理後資料列 | 3,580 |
| 唯一站點 | 1,790 |
| 原始缺失儲存格 | 0 |
| 移除的重複站點快照 | 0 |
| 非營運狀態紀錄 | 58 |
| 有不可用車柱的紀錄 | 959 |
| 有效相鄰快照區間 | 1,761 |
| 車輛數有變化的區間 | 859 |

這兩個快照相隔約 15 分鐘，只足以驗證管線與變化計算，不能代表長期使用模式。

## 6. 如何執行

先啟用環境：

```bash
source .venv/bin/activate
```

下載一份新快照：

```bash
python src/collect_youbike.py
```

重新產生清理資料與報告：

```bash
python src/prepare_data.py
```

執行自動化測試：

```bash
python -m unittest discover -s tests -v
```

## 7. 目前可以與不可以下的結論

目前可以確認：

- 官方資料結構可被穩定載入與驗證。
- 清理流程可處理多個快照並保留資料品質資訊。
- 相鄰快照的站點車輛淨變化可以一致地計算。
- 產物可由固定樣本重現，核心規則有自動化測試保護。

目前不可以宣稱：

- 859 個變化區間等於 859 筆租借事件。
- 兩個快照足以描述尖峰、平假日或天氣影響。
- 已有可訓練、可泛化的 30／60 分鐘預測模型。
- 已有 RMSE、F1-score 或調度最佳化成果。

## 8. 下一階段

下一階段應先持續累積固定頻率的歷史快照，目標至少涵蓋多個完整工作日與週末。資料量足夠後再進行：

1. 檢查時間間隔缺口與站點上下線變化。
2. 建立小時、星期、平假日與尖峰時段特徵。
3. 分析缺車、滿站與淨流入／流出模式。
4. 整合官方天氣資料。
5. 定義不會造成未來資訊洩漏的訓練、驗證與測試切分。

## 9. 作品集口頭說明範例

> 我先從臺北市官方每分鐘更新的 YouBike 站點資料建立可重跑的蒐集與清理管線。流程會驗證必要欄位、轉換數值與臺北時區、保留不可用車柱，並只在連續營運快照之間計算車輛淨變化。我特別沒有把這個淨變化直接稱為租借需求，因為其中可能包含還車與人工調度。目前兩份固定樣本用於確保流程可重現，下一步會累積跨工作日與週末的歷史資料，再建立時間特徵與預測目標。
