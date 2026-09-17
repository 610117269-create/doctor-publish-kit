# 交付结构 v0.1

一个交付包包含 article.json（排版唯一输入）、article.md、wechat.html、visual-brief.md、review.md。标题备选和来源核查记录可写在review.md。

article.json字段：
- schema_version：1。
- title、summary、audience、updated：非空字符串；updated为YYYY-MM-DD。
- status：draft / needs_clinician_review / clinician_reviewed。
- brand：name、byline、color（#加六位十六进制颜色）。byline可为空，不擅自填写资质。
- review：仅clinician_reviewed时必填，包含reviewer、date、version。
- sections：非空数组，每项heading及非空paragraphs。
- paragraphs：每项text和source_ids数组。与医学无关的编辑语可用空数组。
- sources：非空数组，每项id、institution、title、url、accessed（YYYY-MM-DD）。ID唯一；只接受HTTP/HTTPS链接。

不支持Markdown内嵌、原始HTML或图片字段；正文输入纯文本，脚本做HTML转义。图像单独交付，微信编辑器手动插入。

review.md保留：版本、来源支持关系、关键差异、未完成项、检查结果、医生确认记录。visual-brief.md保留：每图目的、位置、画面、可见文字、医学限制、素材授权状态。

重复生成到已有目录时默认拒绝覆盖；确认要重新排版后使用 `--overwrite`，或另选版本目录。
