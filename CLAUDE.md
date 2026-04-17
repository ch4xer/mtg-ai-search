# AI驱动的万智牌查卡器

## 动机

目前，万智牌玩家在寻找特定卡牌时，必须要依赖关键字的精准匹配，这对于一些不太熟悉卡牌名称的玩家来说是一个挑战。因此，我希望开发一个AI驱动的查卡器，让玩家输入较为模糊的描述性语言时也能找到相关的卡牌。

## 方法

将colors、color_identity、keywords、cmc、loyalty、rarity、produced_mana 加入向量化文本，如果不存在相应的字段，则省略

1. **卡片数据收集与处理**：首先，收集万智牌的卡牌数据，包括卡牌名称、类型、颜色、能力描述、卡图等信息。这些数据可以从官方数据库或第三方网站获取。
2. **卡片数据存储**：将卡片文本数据存储在结构化数据库中，图像数据存储在本地。
3. **卡片向量数据库**：使用向量数据库来存储卡牌的文本信息。文本信息通过预训练的语言模型转换为向量，转换方法在embedding.py中有
4. **异能数据获取**：考虑到万智牌中存在一些异能关键词（例如Lifelink），这些关键词需要通过解析规则文本文件keyword_ability.txt来获得每个异能的详细解释，获取的方法写在了chunk.py中
5. **异能数据向量化**：将每一个异能的解释文档转化为向量并存储在向量数据库中，步骤与第三步类似
6. **搭建AI驱动的查询网站**：开发一个用户友好的网站，允许玩家输入描述性语言来搜索卡牌，工作流如下：
7. 用户输入查询文本（中英文都行）
8. Deepseek模型阅读文本，使用英语从异能向量数据库中查询可能相关的异能
9. Deepseek进一步生成卡片描述信息，其中包含了卡片可能携带的异能，并在向量数据库中进行搜索
10. 找到卡牌后，Deepseek会再次阅读卡片文本，按照相关度排序展示给用户。

## 界面设计

1. 要求界面和字体使用中世纪奇幻风格主题，同时保持简洁
2. 支持明暗主题切换
3. 在移动设备和桌面浏览器中均有较好的排版
4. 使用前后端分离设计，前端使用React或其他成熟的前端框架

## 其他

1. 后端使用langgraph或者langchain
2. 通过环境变量提供 `DEEPSEEK_API_KEY`

## 需要修复的问题

1. Add a button in the deck detail page. When user click it, the system will collect all text information of the cards and count duplicate items, like "3x Lightning Bolt <other card information>", then send the deck content to Deepseek, which will analyse the deck's overall strategy and playstyle, helping users quickly understand and get familiar with how to pilot the deck. It will also provide key cautions and important considerations when playing the deck, as well as suggestions for potential future optimizations and improvements notes on the usage. The output of Deepseek should contains the following sections:

- deck_summary: 一句话概括这个卡组的核心玩法风格（1-2 句）,
- playstyle: 详细的对战思路和核心打法（200字以内）,
- weaknesses: 这个卡组的主要弱点/容易被针对的地方

Finally, the AI-generated analysis and suggestions will be automatically saved to the deck’s record in the database. The saved analysis will be displayed at the top of the right-side Deck Analysis panel. The next time the user clicks the “Analyze Deck” button, the system will refresh and update the information in that panel with the latest analysis.

The style of “Analyze Deck” button should be consistent with catppucin theme, while have color indicating its intelegence.
