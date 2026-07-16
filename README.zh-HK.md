# legal-less

**可核證、可追溯的香港法院研究工具：定位裁判理由，並在不把相關性扭曲成指控的前提下整理法律代表紀錄。**

[English README](README.md)

> **專屬方程式：法院立場（Court position）＋法律推理（legal reasoning）＝ 裁判理由候選（ratio decidendi candidate）。**

本儲存庫包含兩個互相關連、但分析上彼此獨立的項目。**項目一**只處理香港終審法院判案書，按段落定位可核證的裁判理由候選，並回答五條必要問題。**項目二**把經操作人員審核的每日聆訊表紀錄，與最終判案書內的律師行代表紀錄作精確比對。項目二屬於**證據地圖**，並非失當行為偵測器、疏忽分類器、勝負統計或律師排名服務。

## 目前實作

| 項目 | 已完成能力 | 刻意保留的界線 |
|---|---|---|
| **終審法院裁判理由定位器** | 核證法院身分；解析案件編號、當事人、法官、爭議、訟費及編號段落；按透明特徵排列裁判理由候選；輸出 JSON 及 Markdown | 分數只用作排列可覆核候選，不能自動宣布法律真理 |
| **法律代表證據地圖** | 驗證 CSV；標準化案件編號及律師行名稱；保留匿名；精確連結案件與律師行；抑制不可靠比率 | 不設無人監督的爬蟲、不揭露「A Firm」身分、不對個別執業者排名、不推斷責任或因果 |

首個公開版本採用**本機證據工具**模式。資料取得權限、保留期限、覆核及發布決定均由操作人員控制。HK Court Diary 的私隱政策及免責聲明限制每日聆訊表個人資料的預定用途，並警告經解析的資料可能出錯。[1] [2] 香港司法機構亦把網上聆訊表結果描述為參考資料，並訂有版權及依賴限制。[3] [4] 因此，本儲存庫不包含批量爬取或公開存檔功能。

## 五條必要問題

每份終審法院報告均須回答以下問題，並保留證據段落：

| 編號 | 問題 | 系統處理方式 |
|---:|---|---|
| 1 | **案件在哪裏審理？** | 以終審法院標題，加上 HKCFA 中立引述或終審上訴編號核證法院；除非來源明示，否則不虛構法院大樓或法庭。 |
| 2 | **誰是當事人？** | 從判案書前頁擷取所有當事人及訴訟身分，並保留法院匿名安排。 |
| 3 | **爭議是甚麼？** | 優先採用明示的 issue、question of law 或 “this appeal concerns” 段落，而非生成概括敘述。 |
| 4 | **哪一方承擔或取得訟費？** | 報告判令中的實際訟費文字；不會單憑勝負推斷訟費。 |
| 5 | **法院如何適用裁判理由？** | 配對法院立場與法律推理；如能定位，再加入適用段落。每項均保留段落編號、分數及警告。 |

## 裁判理由候選模型

定位器按段落運作。候選必須同時具備**法院立場**及**法律推理**。正面訊號包括 “we hold”、 “we conclude”、 “for these reasons”、 “because”、成文法解釋、先例處理及把原則套用於本案事實。當文字只屬當事人陳詞、下級法院描述、程序歷史、旁論、異議、假設情況或只有訟費結果時，系統會扣分或排除。

輸出會區分五條問題、法院立場、法律推理、實際套用、判令、訟費、分數及限制。每份報告亦記錄來源網址、擷取時間、解析器版本及 SHA-256 雜湊值。

## 安裝

本項目需要 **Python 3.11 或以上**。

```bash
gh repo clone LooperRA/legal-less
cd legal-less
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

開發及測試：

```bash
pip install -e '.[dev]'
pytest
ruff check src tests
```

## 項目一：分析終審法院判案書

操作人員須提供其有權處理的 UTF-8 文字、Markdown 或 HTML 檔案。指令不會連線下載；`--source-url` 只作來源紀錄。

```bash
legal-less cfa analyze judgment.html \
  --source-url 'https://www.hklii.hk/en/cases/hkcfa/2025/8' \
  --json-output output/case.json \
  --markdown-output output/case.md
```

返回碼 `0` 表示文件已核證為終審法院材料；返回碼 `2` 表示法院身分未能核證，文件屬範圍以外。

## 項目二：建立法律代表證據地圖

項目二使用**每行一個律師行紀錄**的經審核 CSV。先從本機判案書擷取代表資料：

```bash
legal-less representation extract-judgment judgment.html \
  --judgment-date 2025-05-20 \
  --source-url 'https://www.hklii.hk/en/cases/hkcfa/2025/8' \
  --retrieved-at '2026-07-16T14:00:00+08:00' \
  --case-name '經覆核的案件名稱' \
  --outcome '經覆核的判令' \
  --csv-output data/judgment-representations.csv
```

擷取器只建立 `firm_role=representative` 紀錄。只有在判案書明文支持、並經人工覆核後，才可把律師行標示為案件當事人，或把訴訟人與律師行的關係標示為 `current_client` 或 `former_client`。上述兩個關係值均必須附有 `relationship_evidence`。

其後以範本準備獲准處理的聆訊表紀錄，並執行：

```bash
legal-less representation compare \
  data/cause-list.csv \
  data/judgment-representations.csv \
  --minimum-case-count 5 \
  --json-output output/representation.json \
  --markdown-output output/representation.md
```

確認連結必須同時符合**完全相同的標準化案件編號**及**完全相同的標準化律師行名稱**。未配對紀錄會保留原因；系統只會表示在所提供資料庫中未找到精確配對，不會宣稱判案書不存在。

完整欄位規則載於 [`docs/DATA_SCHEMAS.md`](docs/DATA_SCHEMAS.md)，可複製的空白結構載於 [`examples/`](examples/)。

## 私隱及證據保障

| 保障 | 強制行為 |
|---|---|
| **精確證據連結** | 只有案件編號及律師行名稱均相符，才會確認最終判案書連結；相似當事人名稱不能單獨確認。 |
| **匿名律師行** | 「A Firm」等標籤按案件分隔，不跨案件合併，不嘗試揭露真實身分。 |
| **最低數量抑制** | 低於操作人員設定的不同案件門檻時，不顯示暫停事件比率；匿名律師行永遠不顯示比率。 |
| **不對個人排名** | 系統不彙總或排名個別大律師、律師或其他專業人士。 |
| **不推斷因果** | 聆訊狀態與最終結果保持分開；報告重複列出非因果警告。 |
| **客戶來源申索必須核證** | 只有律師行本身為案件當事人、關係標示為現任／前客戶，且有明示證據時，才會計算。 |
| **原始資料留在本機** | 操作人員提供的判案書、聆訊表及工作資料預設不加入版本控制。 |

> **重要提示：** 即使全部資料來自公開紀錄，彙總及發布仍可能造成名譽及私隱風險。分享報告前，必須覆核每項來源、配對、關係註解及發布目的。

## 驗證狀況

儲存庫現有 **14 項確定性測試**，涵蓋法院核證、案件編號、當事人、五條問題、方程式分數及扣分、來源雜湊、範圍外文件、律師行及案件標準化、匿名標籤、精確連結、最低數量抑制、客戶關係證據、代表資料擷取及所有指令輸出。

解析器亦曾以兩種真實的公開終審法院格式作人工驗證：`[2024] HKCFA 31` 及 `[2025] HKCFA 8`，但判案書全文沒有加入儲存庫。[7] [8] 驗證紀錄見 [`research/phase6_real_validation.md`](research/phase6_real_validation.md)。

## 限制

分數只能排列文字候選，不能單憑分數判定權威性。分開判詞、協同或異議判詞、引用材料、沒有段落編號的判案書、中文獨有格式、掃描檔及非常規排版，均可能需要人工法律分析。報告不能取代閱讀完整判案書或取得法律意見。

法律代表證據地圖的完整性取決於操作人員所提供的資料範圍。聆訊表事件不是最終結果；判案書亦可能省略較早階段的代表、使用不同律師行名稱、涉及相關但不同的程序，或不在所提供的資料集中。系統刻意寧可保留未配對，也不作推測連結。

## 參與貢獻

任何修改均須維持證據可追溯性、來源權限、匿名安排及「描述資料不等於責任」的界線。每項解析器修改須加入回歸測試。請勿提交判案書全文、批量聆訊表、私人客戶資料，或任何違反來源條件取得的材料。詳見 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 授權

程式碼按儲存庫的 [MIT License](LICENSE) 發布。各來源文件仍受其本身的版權、私隱、存取及再用條件規管。

## 參考資料

[1]: https://hkcourtdiary.com/privacy "HK Court Diary — Privacy Policy"
[2]: https://hkcourtdiary.com/disclaimer "HK Court Diary — Disclaimer"
[3]: https://e-services.judiciary.hk/dcl/index.jsp?lang=en "香港司法機構 — 每日聆訊表"
[4]: https://www.judiciary.hk/en/other_information/disclaimer.html "香港司法機構 — 版權及免責聲明"
[5]: https://www.hklii.hk/legal "HKLII — Legal Information and Usage Conditions"
[6]: https://www.hkcfa.hk/en/work/cases/judgments/index.html "香港終審法院 — 判案書"
[7]: https://www.hklii.hk/en/cases/hkcfa/2024/31 "[2024] HKCFA 31"
[8]: https://www.hklii.hk/en/cases/hkcfa/2025/8 "[2025] HKCFA 8"
