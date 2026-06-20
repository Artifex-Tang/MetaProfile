# 附件全文本抽取设计（独立 spec）

- 日期：2026-06-20
- 范围：把原始附件文件（PDF/DOCX 等）抽取为干净全文本 `clean_content` 并入库，供 content_miner（实体+关系挖掘）与弱信号提取（见 `2026-06-20-weak-signal-pipeline-design.md`）共用
- 上游：ingest_ods 数据源（附件随主记录）
- 下游：content_miner、WeakSignalExtractor

---

## 1. 背景与技术问题
结构化字段（title/abstract/keyword/applicant）信息密度有限，大量信号藏于附件全文（论文 PDF、项目可研报告、招标文件、政策原文）。现有系统仅消费结构化列，**全文未入语料**，弱信号/挖掘覆盖不全。

技术问题：附件**格式异构**（PDF/DOCX/扫描件）、**质量参差**（乱码/页眉页脚/断行）、**量大**（需幂等增量），需一个鲁棒、可复用、可幂等的全文本抽取组件。

## 2. 输入
- 来源：ODS 记录关联的附件（文件路径或二进制 blob，随数据源配置）。
- 格式：PDF（文本型优先，扫描型回退 OCR）、DOCX、（可选）TXT/HTML。
- 元数据：`source_id`（所属数据源）、`doc_id`（主记录 id）、`mime`、`filename`、`record_time`（主记录时间，用于分窗）。

## 3. 抽取流程
### 3.1 路由（按 mime）
- `application/pdf` → PDF 分支
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` / `.docx` → DOCX 分支
- `text/plain` / `text/html` → 直读 + 去 tag

### 3.2 PDF 分支
1. `pdfplumber` 按页提取文本（保留段落换行）。
2. **文本量判定**：若提取字符数 < 阈值（默认按页均 < 10 字符）→ 判为**扫描件**，回退 OCR。
3. OCR 回退：`paddleocr`（中文优）或 `tesseract`（按可用性），按页 OCR 合并。
4. 失败重试 + 跳过（记录 error，不阻塞批次）。

### 3.3 DOCX 分支
`python-docx`：遍历段落 + 表格单元格文本，保留段落分隔。

### 3.4 清洗（Clean）
- 去页眉页脚（重复模式行检测：跨页高频且短的行剔除）。
- 去乱码（非可打印字符占比 > 阈值的段剔除）。
- 合并断行（行尾无标点且下行首字母小写/续接 → 合并）。
- 规范空白（多空格/制表符 → 单空格，全角半角统一）。
- 输出 `clean_content`（纯文本，UTF-8）。

## 4. 入库与幂等
- 表 `attachment_text`（新）：`id, source_id, doc_id, filename, mime, clean_content(TEXT), char_count, extracted_at, status(ok/ocr/failed), error_msg, created_at, updated_at`。
- **唯一键** `(source_id, doc_id, filename)`，冲突 → 跳过（已抽取）。
- 增量：ingest 时只处理未在表的附件。

## 5. 集成点
- **content_miner**（已有 T11）：消费 `clean_content` 做 LLM 实体+关系挖掘（无需改 content_miner，其已 `att.get("clean_content")`）。
- **WeakSignalExtractor**（弱信号 spec）：附件 `clean_content` 作为第 4 语料源，参与 TF-IDF/突现/NER。
- **ingest_ods collector**：附件抽取作为 collector 新阶段（结构化灌库后触发）。

## 6. 组件接口
```python
class AttachmentExtractor:
    async def extract_text(self, *, payload: bytes | str, mime: str, filename: str) -> AttachmentText: ...

@dataclass
class AttachmentText:
    clean_content: str
    char_count: int
    status: str          # ok / ocr / failed
    method: str          # pdfplumber / docx / ocr / plain
    error: str | None
```

## 7. 实施步骤（后续 writing-plans 细化）
1. `attachment_text` 表 + migration。
2. `AttachmentExtractor`（PDF/DOCX/OCR/清洗）。
3. collector 附件阶段（读附件 → 抽取 → 入库，幂等）。
4. 单测（各格式样例 + 乱码/扫描件回退 + 幂等）。

## 8. 创新点 / 有益效果
- 多格式统一抽取（PDF/DOCX/扫描件 OCR 回退），鲁棒。
- 清洗规则去页眉页脚/乱码/断行，提升下游 NLP 质量。
- 幂等增量，支持大批量附件断点续抽。
- 全文入语料，使弱信号/挖掘覆盖结构化字段之外的深度信号（弱信号创新点 5 的支撑）。
