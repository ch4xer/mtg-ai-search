# MTG AI Search 系统规格说明

本文档用自然语言描述 MTG AI Search 的完整产品、数据、接口、后台任务和运行要求。目标是让未来开发者只拿到这份规格，也能重新实现同等功能的系统。

## 1. 产品定位

MTG AI Search 是一个面向万智牌玩家的卡牌搜索与卡组管理系统。用户可以用自然语言描述想要的卡牌效果，也可以用精确筛选条件查找卡牌；登录用户可以创建卡组、导入导出牌表、切换卡图版本、生成卡组分析，并分享卡组链接。系统支持英文和简体中文界面，中文界面下优先展示卡牌中文文本信息，卡图始终使用 Scryfall 英文卡图。

系统由三部分组成：

- Web 前端：React 单页应用。
- 后端 API：FastAPI 服务。
- 数据库：PostgreSQL 17 + pgvector，用于卡牌数据、搜索索引、用户、卡组、后台任务状态等。

## 2. 用户角色

系统有三类访问状态：

- 未登录用户：可以使用 AI Search 和 Exact Match，但受匿名搜索频率限制；不能保存卡组。
- 普通登录用户：可以搜索、创建卡组、管理自己的卡组、生成 API key、修改密码；受登录用户搜索频率限制。
- 管理员：拥有普通用户能力，并可访问后台管理页，管理用户、维护数据、调整搜索频率限制、导出数据库卡牌数据；管理员不受普通 AI 搜索频率限制。

管理员账号可以通过环境变量 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 在启动时创建或提升。如果同名用户已存在，启动流程应把它提升为管理员，并在环境变量密码变化时更新密码。

## 3. 核心数据来源

### 3.1 Scryfall

系统的英文卡牌数据来自 Scryfall `all_cards` bulk data。导入时只保留英文印刷版本，即 `lang == "en"`，并排除 emblem、art series 等不作为普通卡牌搜索结果的对象。Token 和 minigame 对象允许进入卡牌库并可在搜索结果中展示。

系统需要保存：

- 以 `oracle_id` 为主键的卡牌聚合信息。
- 每个英文印刷版本的 set、collector number、rarity、artist、flavor text、released date、image URLs、card faces 等信息。
- Scryfall 卡图 URL，包括 small、normal、large、png、art_crop、border_crop。

系统不下载并永久保存 Scryfall 图片文件；导出 PDF/ZIP 时可以按需下载并短期缓存图片文件。

### 3.2 Scryfall Tagger

AI Search 使用 Scryfall Tagger 的 function tags。系统从 Scryfall Tagger 页面同步 tag 列表，并通过 Scryfall 搜索 API 获取每个 function tag 对应的卡牌集合，写入本地 `card_tagger_tags` 关系表。

系统仅使用 function tags 作为 AI Search 的检索目标。Art tags 虽然存在于 Tagger 页面，但不参与 AI Search 检索。`tag_type` 在最底层的 SQL 查询和 catalog DB 中硬编码为 `function`，中间数据结构不携带 `tag_type` 字段。

每个 function tag 通过 LLM 批量生成 expansion（aliases、retrieval_phrases、description），然后通过 SiliconFlow embedding API（Qwen3-Embedding-4B，2560 维）生成向量，存储在 tagger_tags.embedding 列中。向量搜索使用 PostgreSQL halfvec 余弦距离。

### 3.3 MTGCH

中文卡牌文本来自 MTGCH API，也就是“大学城废墟”接口。系统只同步中文文本信息，不同步中文图源，不保存中文卡图 URL。

需要保存的中文字段包括：

- 中文卡名。
- 中文类别。
- 中文规则文本。
- 中文背景叙述。
- 中文系列名。
- 双面牌每一面的中文文本信息。

MTGCH 同步应读取官方中文字段和 fallback 翻译字段。对于普通牌，应优先使用 `zhs_*` 官方字段；如果官方字段为空，应使用 `atomic_translated_*`、`atomic_official_name`、`full_translated_name` 等可用字段。对于双面牌，应读取 `other_faces` 并按 `face_index` 排序。

中文同步不是系统启动流程的一部分，也不是 Scryfall 常规同步流程的一部分。它只能由后台“中文卡牌信息”按钮触发。

## 4. 语言与卡牌展示规则

系统界面支持英文和简体中文。用户可以在顶部导航中切换语言，语言偏好保存在浏览器 localStorage。

界面语言影响所有用户可见文案，也影响卡牌文本展示：

- 当前界面是英文时，搜索结果和卡组详情展示英文卡牌信息。
- 当前界面是中文时，搜索结果和卡组详情优先展示 `card.zh` 中的中文卡牌文本。
- 如果某张卡没有中文信息，中文界面也必须回退展示英文信息。
- 卡图始终使用英文 Scryfall 卡图；不要使用中文卡图。
- 切换语言后，当前已经显示的搜索结果和卡组详情中的卡牌文本应立即切换，不需要重新搜索。
- 卡牌如果有中文名，展示中文名时可以同时展示英文名作为次级名称，帮助用户识别。
- 双面牌在中文界面下应按当前面展示对应面的中文文本；如果某一面缺中文，回退到该面的英文文本。

搜索结果 API 与卡组卡牌 API 都应返回英文基础字段，同时在有中文时返回 `zh` 对象。中文对象按卡牌维度关联，即只要同一个 `card_id/oracle_id` 下任一同步过的中文记录可用，搜索结果和卡组详情就应能使用它；不要要求中文记录的 `print_id` 与当前展示的英文印刷版本完全一致。

## 5. 搜索功能

### 5.1 AI Search

AI Search 是默认首页搜索模式。用户输入自然语言需求，例如”蓝色能反击咒语并抓牌的牌”。系统应执行以下流程：

1. 接收用户 query。
2. 对未登录用户和普通用户做每小时搜索次数限制；管理员不受限制。
3. **约束提取（LLM 调用 1）**：使用 LLM 从自然语言中提取结构化约束，包括：
   - 卡牌筛选条件：颜色（支持 `any:` 交集、`=` 精确、`excluded_colors` 排除）、类别、CMC、power/toughness、发售日期、layout。
   - 检索目标（targets）：原子化的游戏效果描述，每个 target 包含 slot 和 intent，多个效果必须拆分为独立 target。
   - 布尔逻辑树（logic）：and/or 操作符节点，表达 targets 之间的关系。
   - 如果 query 只是卡名没有游戏意图，返回空 targets，系统退化为纯结构化筛选。
4. **向量检索**：将每个 target 的 intent 文本编码为 embedding，在 function tag catalog 中做向量余弦相似度搜索，每个 target 返回 top-40 候选 tags。多 target 时合并去重（同 tag 取最高分）。
5. **Tag 选择**：如果每个 target 的 top-1 分数明显领先（≥ 第二名 × 1.45 且分差 ≥ 0.006），直接使用 top-1，跳过 LLM。否则调用 LLM 重排序（LLM 调用 2），从 top-20 候选中选择最能满足请求的 tag 组合，不得发明 tag。
6. **Tag 覆盖保证**：确保每个 target slot 至少有一个 tag 被选中；如果缺失，从候选池中补充该 slot 的最高分 tag。
7. **SQL 布尔逻辑求值**：使用 PostgreSQL `bool_or(slot = $N)` 聚合函数在 HAVING 子句中求值逻辑树，将 tags 转换为匹配的卡牌集合。
8. **结构化筛选**：将步骤 3 抽取的颜色、类别、CMC 等筛选条件应用于卡牌结果。
9. 返回分页卡牌结果。首次搜索创建 ai_search_sessions 记录保存 search plan；加载更多时使用 search_id 复用计划，避免重复调用 LLM。

整个搜索流程最多 2 次 LLM 调用（约束提取 + tag 重排序），在分数分布极端时可降至 1 次。

AI Search 应返回：

- `search_id`：后续加载更多使用。
- `results`：卡牌列表。
- `total`：当前搜索计划下总卡牌数。
- `limit`、`offset`、`has_more`。

AI Search 前端行为：

- 首页显示 AI Search tab。
- 首次进入无结果时展示功能说明卡片。
- 搜索中展示 loading。
- 无结果展示空状态。
- 有结果时用卡牌网格展示，并支持“加载更多”。
- 每张卡支持切换展示卡图模式、选择印刷版本、加入卡组。

### 5.2 Exact Match

Exact Match 是确定性筛选搜索，不依赖 AI Search 的 tag 选择流程。用户可以输入关键词，也可以使用筛选器。

支持筛选项：

- 文本关键词 `q`。
- 颜色：W/U/B/R/G，多选。
- 类型：Creature、Instant、Sorcery、Enchantment、Artifact、Land、Planeswalker、Battle 等。
- 子类别。
- 稀有度：common、uncommon、rare、mythic。
- 关键字能力。
- mana value 最小/最大。
- power 最小/最大。
- toughness 最小/最大。
- 是否包含 playtest/unofficial 卡牌。

Exact Match 查询规则：

- 如果 `q` 包含中文字符，则应在中文卡牌信息表中搜索中文卡名、中文类别、中文规则文本、中文背景叙述、中文系列名。
- 如果 `q` 不包含中文字符，则在英文 cards 表中的 name、type_line、oracle_text 搜索。
- 即使用中文搜索，返回的卡图仍然使用英文 Scryfall 卡图。
- 搜索结果应返回 facets，用于前端展示可选颜色、类型、稀有度、关键字、子类别、mana/power/toughness 范围。
- 默认不展示 unofficial/playtest 卡，除非用户显式开启。

Exact Match 前端行为：

- 路由为 `/exact-match`。
- 筛选器应以可收起的工具条形式展示。
- 颜色用 mana symbol 按钮。
- 类型、稀有度用下拉框。
- 数值范围用数字输入。
- 能力关键字用多选菜单。
- 子类别用输入框加 datalist。
- 有结果时分页展示。

## 6. 卡牌卡片展示

所有搜索结果和卡组详情中的卡牌卡片应使用统一展示规则：

- 支持 `art_crop` 和 `border_crop` 两种图片显示模式，用户可在搜索页切换，并保存到 localStorage。
- 普通卡优先使用当前选择印刷版本的图片，否则使用默认英文印刷版本图片。
- 双面牌显示翻面按钮，前后面图片分别使用对应 face 的 image_uris。
- 图片加载失败时显示卡牌名称占位。
- art crop 模式下可以叠加展示 flavor text。
- 卡牌信息区域展示名称、mana cost、类别、规则文本、力量/防御/忠诚、系列图标、稀有度、合法性等。
- mana cost 和 oracle text 中的 mana 符号应解析为 mana-font 图标。
- 每张卡提供“选择卡图版本”按钮，打开该卡所有本地英文印刷版本的图片选择器。
- 已登录用户或持有本地 token 的用户可以从卡片上把卡加入自己的卡组。

## 7. 认证与账号

系统使用 JWT access token 和 refresh token。

注册要求：

- 用户名。
- 密码。
- 邮箱。

登录返回：

- access token。
- refresh token。
- user 对象。

前端应把 token 存入 localStorage，并在 API 请求中自动携带 access token。access token 过期时，前端应使用 refresh token 自动刷新一次；刷新失败则清除本地登录状态。

邮箱验证：

- 注册后可发送邮箱验证码。
- 用户可提交验证码完成邮箱验证。
- 验证失败次数过多时应提示用户重新获取验证码。
- 如果未配置 Resend API key，邮件功能应明确失败，而不是静默成功。

密码修改：

- 登录用户可以在设置页请求密码修改验证码。
- 用户输入验证码和新密码后修改密码。
- 新密码长度必须至少 6 个字符。

API key：

- 登录用户可以在设置页生成或重新生成 API key。
- API key 只在生成时明文显示一次。
- 数据库只保存 API key 的 SHA-256 hash。
- API key 以 `mtg_` 为前缀。
- 外部 API 使用 API key 认证。

## 8. 卡组管理

### 8.1 卡组列表

登录用户可以访问 `/decks` 查看自己的卡组。每个卡组卡片显示：

- 卡组名称。
- 赛制。
- 主牌数量/总卡牌数量。
- 颜色标识。
- 卡组封面图，如果设置过封面。

用户可以创建新卡组。创建时需要名称和赛制，赛制可为 undefined 或支持的 MTG 构筑赛制。

### 8.2 卡组详情

卡组详情页应展示：

- 卡组标题、返回按钮、重命名、赛制切换、分享、导入、导出、删除等操作。
- 左侧或主区域卡牌分组展示。
- 卡牌预览面板。
- 卡组统计/分析面板。
- 移动端底部卡牌详情弹层。

卡牌分组规则：

- 主牌和备牌分开。
- 主牌按服务端返回的 deck_type 分组，按 deck_type_sort 排序。deck_type 值：Planeswalker、Creature、Sorcery、Instant、Artifact、Enchantment、Battle、Land、Other。
- 分组标签跟随界面语言显示。
- 分组内按 mana value、颜色、本地化名称等稳定排序。

卡组详情中的卡牌文本必须跟随界面语言，中文界面优先显示中文文本，缺中文时回退英文；卡图仍为英文图。

### 8.3 卡组编辑

卡组所有权规则：

- 只有卡组拥有者可以修改卡组。
- 共享访问者只能查看。

拥有者可以：

- 添加卡牌。
- 增减数量。
- 删除卡牌。
- 在主牌和备牌之间移动一张或全部。
- 拖拽卡牌移动区域。
- 移动端长按打开移动面板。
- 右键打开菜单，将一张牌移到另一牌区，或设为卡组封面。
- 切换某张牌在卡组内使用的印刷版本/卡图。
- 重置卡图到默认版本。

卡牌合法性：

- 使用卡牌 `legalities` 判断当前赛制合法性。
- 非 legal/restricted 状态应在卡组中标记问题。
- 前端应显示卡组是否合法、问题数量和每张牌的问题提示。

### 8.4 导入与导出

导入牌表：

- 支持每行 `数量 卡名`。
- 支持 `数量 卡名 (SET) COLLECTOR_NUMBER`。
- 支持主牌/备牌标题，如 `SIDEBOARD`、`MAINBOARD`。
- 空行在备牌段落后可回到主牌。
- 双面牌名称导入时取正面名称。
- 如果本地无法按名称匹配，应尝试通过 Scryfall named 查询解析。
- 返回已添加列表和未找到列表。

导出文本：

- 导出主牌行 `数量 卡名`。
- 如有备牌，空一行后输出 `SIDEBOARD`，再输出备牌行。
- 导出使用英文卡名。

导出 PDF：

- 输出 A4 尺寸 PDF。
- 每页 3x3，即 9 张卡。
- 使用 PNG 卡图。
- 双面牌应包含背面图。
- 导出过程通过 SSE 返回进度，完成后返回 export_id，再通过下载端点下载。

导出 ZIP 图片包：

- 下载并打包卡组中所有需要的 PNG 卡图。
- 使用同样的 SSE 进度和 export_id 下载流程。

图片下载缓存：

- 导出时可按 URL 做短期文件缓存，减少重复下载。
- 如果有卡缺失 PNG URL，导出应失败并说明缺失卡牌。

### 8.5 卡组分析

用户可以对卡组执行 AI 分析。分析结果应包含中英文两套内容，供前端按当前语言显示。

分析面板还应本地计算：

- 色组分布。
- mana curve。
- 稀有度分布。
- 卡牌类型分布。
- 最近分析时间。
- 卡组修改后分析是否过期。

## 9. 后台管理

后台路由为 `/admin/:section`，只有管理员可访问。后台包含 Dashboard、Users、Database、Settings 四个区域。

### 9.1 Dashboard

应展示系统统计，包括用户数、卡牌数、搜索次数、最近活动等。具体统计来自数据库聚合接口。

### 9.2 Users

管理员可以：

- 分页查看用户。
- 按关键词搜索用户名或邮箱。
- 查看用户角色、邮箱验证状态、最后活跃时间、创建时间。
- 将用户在 admin 和 user 之间切换。
- 删除用户。
- 不允许删除自己。

### 9.3 Database Maintenance

后台数据库维护区包含以下任务卡片：

- Keyword sync：同步关键字能力，用于 Exact Match 能力筛选。
- Function tag links：同步 Scryfall Tagger function tags 与卡牌关系，用于 AI Search。
- Function tag embeddings：生成或补全 function tag 的语义扩展文本和 embedding。
- Chinese card info：从 MTGCH 补全缺失的中文卡名、类别、规则文本、背景叙述和系列名。
- Export card data：导出卡牌相关数据库数据。

维护任务必须串行执行，同一时间只允许一个会写大量数据的后台维护任务运行。如果有任务正在运行，其他任务按钮应禁用，后端也应返回 409。

后台维护卡片应等高展示，按钮贴在卡片底部，保持视觉对齐。

### 9.4 Scryfall 数据同步

Database Maintenance 下还有常规卡牌数据同步区：

- Manual sync：检查 Scryfall bulk data updated_at，如果无变化则跳过。
- Force refresh：忽略本地 updated_at，强制执行同步。

同步应记录到 `sync_logs`，包含状态、开始/完成时间、新增卡牌数、更新卡牌数、消息。前端应展示同步日志。

### 9.5 Settings

管理员可以调整 AI Search 频率限制：

- 匿名用户每小时搜索次数。
- 登录用户每小时搜索次数。

设置保存到 `app_meta`，启动时加载到内存配置。

## 10. 外部 API

系统提供 API key 保护的外部接口，供第三方程序调用。

### 10.1 AI Search API

Endpoint：`POST /api/external/ai-search`

请求字段：

- `api_key`：必填。
- `query`：自然语言查询。
- `limit`：1 到 50，默认 10。

返回 `SearchResponse`：results、total、limit、offset、has_more 等。

### 10.2 Exact Match API

Endpoint：`POST /api/external/exact-match`

请求字段：

- `api_key`：必填。
- `query`：文本关键词。
- colors、types、rarities、keywords、subtypes、cmc_min、cmc_max、power_min、power_max、toughness_min、toughness_max、include_playtest。
- `limit`：1 到 100。

返回 `SearchResponse`。

## 11. HTTP API 规格

### 11.1 Auth

- `POST /api/auth/register`：注册，返回 token 和 user。
- `POST /api/auth/login`：登录，返回 token 和 user。
- `POST /api/auth/refresh`：用 refresh token 换 access token。
- `GET /api/auth/me`：返回当前用户。
- `POST /api/auth/verify-email`：提交邮箱验证码。
- `POST /api/auth/resend-verification`：重新发送邮箱验证码。
- `POST /api/auth/request-password-change`：发送改密验证码。
- `POST /api/auth/change-password`：提交验证码和新密码。
- `GET /api/auth/api-key`：查询是否已有 API key。
- `POST /api/auth/api-key`：生成或重新生成 API key。

### 11.2 Search

- `POST /api/search`：AI Search。接受 `query`、`limit`、`offset`、`search_id`（加载更多）、`include_zh`。返回 `SearchResponse`（search_id、results、total、limit、offset、has_more）。
- `POST /api/discover`：Exact Match。
- `GET /api/keywords`：返回所有关键字能力。
- `GET /api/cards/{oracle_id}/prints`：返回指定卡牌的所有英文印刷版本。

### 11.3 Decks

需要登录：

- `GET /api/decks`：当前用户卡组列表。
- `POST /api/decks`：创建卡组。
- `GET /api/decks/{deck_id}`：获取自己卡组摘要。
- `PUT /api/decks/{deck_id}`：重命名或修改赛制。
- `PATCH /api/decks/{deck_id}/cover`：设置封面图。
- `DELETE /api/decks/{deck_id}`：删除卡组。
- `GET /api/decks/{deck_id}/cards`：列出卡组卡牌。
- `POST /api/decks/{deck_id}/cards`：添加或增加卡牌。
- `PATCH /api/decks/{deck_id}/cards/{card_id}`：更新卡牌印刷版本和图片。
- `DELETE /api/decks/{deck_id}/cards/{card_id}`：删除卡牌，可用 query 参数指定 board。
- `POST /api/decks/{deck_id}/import`：导入牌表。
- `GET /api/decks/{deck_id}/export/text`：导出文本牌表。
- `POST /api/decks/{deck_id}/analyze`：生成卡组分析。
- `GET /api/decks/{deck_id}/export/stream`：PDF 导出 SSE。
- `GET /api/decks/{deck_id}/export/download/{export_id}`：下载 PDF。
- `GET /api/decks/{deck_id}/export/images/stream`：ZIP 图片导出 SSE。
- `GET /api/decks/{deck_id}/export/images/download/{export_id}`：下载 ZIP。

公开共享：

- `GET /api/shared/decks/{deck_id}`。
- `GET /api/shared/decks/{deck_id}/cards`。
- `GET /api/shared/decks/{deck_id}/export/text`。
- `GET /api/shared/decks/{deck_id}/export/stream`。
- `GET /api/shared/decks/{deck_id}/export/download/{export_id}`。
- `GET /api/shared/decks/{deck_id}/export/images/stream`。
- `GET /api/shared/decks/{deck_id}/export/images/download/{export_id}`。

### 11.4 Admin

需要管理员：

- `GET /api/admin/stats`。
- `GET /api/admin/users`。
- `PUT /api/admin/users/{user_id}/role`。
- `DELETE /api/admin/users/{user_id}`。
- `GET /api/admin/task-status`。
- `POST /api/admin/reseed`。
- `POST /api/admin/sync-abilities`。
- `POST /api/admin/sync-function-tags`。
- `POST /api/admin/tag-embeddings`。
- `POST /api/admin/sync-card-translations`。
- `GET /api/admin/sync-logs`。
- `POST /api/admin/sync`，可带 `force=true`。
- `GET /api/admin/export/cards`。
- `GET /api/admin/settings`。
- `PUT /api/admin/settings`。

### 11.5 Health

- `GET /api/health`：返回系统初始化状态。前端启动后每 3 秒轮询一次，如果状态为 initializing，则展示系统维护/初始化提示。

## 12. 数据模型

### 12.1 cards

以 `oracle_id` 为主键，保存卡牌聚合信息：

- name、mana_cost、cmc、type_line、oracle_text。
- power、toughness。
- colors、color_identity、keywords。
- legalities JSON。
- layout、card_faces JSON。
- image_set_code、image_set_name、image_collector_number。
- is_unofficial、is_playtest。

### 12.2 card_prints

以 Scryfall card id 为主键，保存英文印刷版本：

- card_id 引用 cards。
- set_code、set_name、collector_num。
- rarity、artist、flavor_name、flavor_text。
- released_at、finishes。
- image_small、image_normal、image_large、image_png、image_art_crop、image_border_crop。
- card_faces JSON。
- image_set_code、image_set_name、image_collector_number。
- set_type、security_stamp、border_color、games。

同一个 card_id 可以有多个 card_prints。

### 12.3 card_print_translations

保存 MTGCH 中文文本信息：

- print_id：引用 card_prints，是主键。
- card_id：引用 cards。
- lang：默认 zhs。
- source：默认 mtgch。
- status：ok、empty、not_found、failed 等。
- name、type_line、oracle_text、flavor_text、set_name。
- card_faces JSON。
- synced_at。
- last_error。

该表不得包含中文图片 URL 字段。历史存在的 `image_uris` 字段应迁移删除。

展示中文时按 card_id 取一条 status=ok 的记录，不要求 print_id 与当前英文展示版本一致。

### 12.4 keyword_abilities

保存 MTG 关键字能力：

- id。
- name。
- description。
- embedding，可为空。

来源为本地 rules 文本解析和后台同步。

### 12.5 tagger_tags

保存 Scryfall Tagger tag catalog：

- tag_type：目前核心使用 function。
- tag、label、normalized。
- aliases、retrieval_phrases、description。
- embedding_text。
- expansion_generated_at、expansion_source、expansion_model、expansion_version。
- embedding。
- content_hash、first_seen_at、updated_at、removed_at。

### 12.6 card_tagger_tags

保存 tag 与本地卡牌的关系：

- tag_type。
- tag。
- card_id。
- source_scryfall_id。
- synced_at。

### 12.7 tag_sync_state 和 tag_card_sync_state

保存 tag catalog 同步状态、每个 function tag 的卡牌关系同步状态、失败原因和计数。

### 12.8 card_effects

保存从 oracle text 拆分出的效果片段（历史表，当前 AI Search 不直接使用，搜索改为基于 function tag 向量检索）：

- id。
- card_id。
- face_index。
- chunk_index。
- effect_text。
- source。
- embedding。

### 12.9 users

保存用户：

- id、username、password_hash、role。
- email、email_verified。
- verification_code、verification_code_expires_at、verification_attempts。
- last_active_at。
- api_key_hash、api_key_created_at。
- created_at。

### 12.10 decks 和 deck_cards

decks：

- id、user_id。
- name、format。
- cover_image_url。
- analysis_data、analysis_updated_at。
- created_at、updated_at。

deck_cards：

- deck_id、card_id。
- print_id，可为空。
- quantity。
- image_url、display_url，用于用户选择的卡图。
- board：mainboard 或 sideboard。
- added_at。
- 每个 deck_id + card_id + board 唯一。

### 12.11 search_logs、ai_search_sessions、sync_logs、app_meta

search_logs：记录 AI Search 请求，用于频率限制和统计。

ai_search_sessions：保存 AI Search 首次搜索生成的 search plan，用于加载更多；应有过期时间。

sync_logs：记录 Scryfall 数据同步历史。

app_meta：保存全局元数据，例如上次 Scryfall updated_at、后台频率限制配置等。

## 13. 后台启动与任务

系统启动流程：

1. 建立数据库连接池。
2. 运行 pre-seed migrations，创建用户、卡组、日志、tagger_tags 等基础表。
3. 创建或提升内置管理员。
4. 如果 cards 表为空，执行完整 Scryfall 导入。
5. 如果 keyword_abilities 为空，初始化关键字能力。
6. 运行 post-seed migrations，创建依赖 cards/card_prints 的表和索引。
7. 从 app_meta 读取持久化设置。
8. 设置 health 状态为 ok。
9. 启动每日 Scryfall 同步循环。
10. 启动 tag expansion/embedding 增量补全任务（如果启用 TAG_BOOTSTRAP_ENABLED）。

初始化失败时应按环境变量配置重试，超过次数后退出进程，让容器重启。

每日 Scryfall 同步：

- 按 CST 午夜执行。
- 检查 Scryfall bulk data 的 `updated_at`。
- 如果 unchanged，跳过。
- 如果 changed，下载 bulk data 并 upsert cards/card_prints。
- 同步完成后更新 app_meta 和 sync_logs。

中文信息同步：

- 只由后台按钮触发。
- 默认对缺失中文记录的本地默认英文印刷版本请求 MTGCH。
- 每批写入数据库。
- 遇到 HTTP 429 应读取 Retry-After 或使用指数退避。
- 默认并发应低，避免触发 MTGCH 限流。
- status=failed 的请求可以不写入，方便下一次继续尝试。
- status=not_found/empty 可以写入，避免重复请求已知无结果的记录。

## 14. 部署与配置

Docker Compose 应包含：

- `mtg-db`：pgvector/pgvector:pg17，暴露 5433 到宿主机，内部 5432。
- `mtg-backend`：构建 backend Dockerfile，暴露 8000。
- `mtg-frontend`：构建 frontend Dockerfile，暴露 60010 到宿主机 80。

必要环境变量：

- `POSTGRES_PASSWORD`。
- `JWT_SECRET`。

AI 相关环境变量：

- `DEEPSEEK_API_KEY`。
- `DEEPSEEK_MODEL`。
- `DEEPSEEK_BASE_URL`。
- `SILICONFLOW_API_KEY`。

后台和邮件：

- `ADMIN_USERNAME`。
- `ADMIN_PASSWORD`。
- `RESEND_API_KEY`。

搜索和 tag 维护：

- `TAG_BOOTSTRAP_ENABLED`。
- `TAG_EXPANSION_BATCH_SIZE`。
- `TAG_EMBEDDING_BATCH_SIZE`。
- `TAG_SAMPLE_SIZE`。
- `TAG_PRINT_EMBEDDING_TEXT`。
- `SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS`。

MTGCH：

- `MTGCH_API_BASE_URL`。
- `MTGCH_API_TIMEOUT_SECONDS`。
- `MTGCH_API_CONCURRENCY`。
- `MTGCH_REQUEST_DELAY_SECONDS`。
- `MTGCH_MAX_RETRIES`。
- `MTGCH_RETRY_BASE_SECONDS`。
- `MTGCH_RETRY_MAX_SECONDS`。
- `MTGCH_SYNC_ENABLED`。
- `MTGCH_SYNC_BATCH_SIZE`。

其他：

- `ALLOWED_ORIGINS`。
- `LOG_LEVEL`。
- `SCRYFALL_BULK_DATA_FILE`，可用于离线或指定 bulk data 文件。

## 15. UI 规格

整体 UI 要求：

- 使用暗色和亮色主题，主题偏好保存到 localStorage。
- 顶部导航提供搜索、卡组、设置、后台入口、语言切换、主题切换。
- Footer 显示 fan content 免责声明和数据来源。
- 所有主要操作失败时显示 toast。
- loading 状态使用 spinner。
- 后台和卡组页面应适配桌面和移动端。

路由：

- `/`：AI Search。
- `/exact-match`：Exact Match。
- `/login`：登录/注册。
- `/decks`：我的卡组。
- `/decks/:id`：卡组详情，拥有者可编辑，非拥有者可查看共享内容。
- `/settings`：账号设置。
- `/admin/dashboard`。
- `/admin/users`。
- `/admin/database`。
- `/admin/settings`。

## 16. 错误处理与权限

权限错误：

- 未登录访问保护路由时前端跳转 `/login`。
- 非管理员访问后台时跳转首页。
- 后端对不存在或无权访问的卡组统一返回 404，避免泄露资源存在性。
- 外部 API key 无效返回 401。

频率限制：

- 匿名用户和普通登录用户按小时限制 AI Search。
- 达到限制返回 429。
- 管理员不受该限制。

后台任务冲突：

- 当维护任务运行时，启动其他互斥任务返回 409。

导出错误：

- 卡组为空时文本导出失败。
- 缺 PNG 卡图时 PDF/ZIP 导出失败，并返回缺失卡样例。
- Range 下载请求非法时返回 416。

## 17. 验收标准

系统实现完成后，应满足以下用户可见行为：

- 新环境启动后可以自动建库、导入 Scryfall 卡牌、进入 ready 状态。
- 用户可以注册、登录、刷新会话、退出登录。
- 管理员可以看到后台页面，并能运行维护任务。
- AI Search 可以用中文或英文自然语言返回相关卡牌，并支持加载更多。
- Exact Match 可以按文本、颜色、类型、稀有度、能力、数值范围筛选卡牌。
- 中文界面下，已同步中文信息的卡牌在搜索结果和卡组详情中显示中文文本；无中文信息的卡牌显示英文。
- 切换界面语言后，当前搜索结果和卡组详情文本同步切换。
- 中文图源不入库、不展示；所有卡图来自英文 Scryfall 数据。
- 用户可以创建卡组、添加卡牌、移动主牌/备牌、调整数量、切换卡图版本、设置封面。
- 卡组合法性提示按赛制工作。
- 卡组可以导入文本牌表，导出文本牌表、PDF 和 ZIP 图片包。
- 共享卡组链接无需登录即可查看和导出。
- 设置页可以生成 API key，外部 API 可用该 key 查询。
- 后台中文信息按钮可以从 MTGCH 补全文本；遇到限流时应退避重试。

## 18. 明确不做的事项

- 不同步中文卡图。
- 不把中文图源保存到数据库。
- 不在启动流程中自动同步 MTGCH 中文信息。
- 不在常规 Scryfall 同步中自动同步 MTGCH 中文信息。
- 不要求每个英文印刷版本都有对应中文记录；展示中文时按 card_id 使用任意可用中文文本记录。
