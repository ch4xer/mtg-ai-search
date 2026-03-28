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
4. **搭建AI驱动的查询网站**：开发一个用户友好的网站，允许玩家输入描述性语言来搜索卡牌，工作流如下：
  1. 用户输入查询文本（中英文都行）
  2. Deepseek模型阅读文本，使用英语从异能向量数据库中查询可能相关的异能
  3. Deepseek进一步生成卡片描述信息，其中包含了卡片可能携带的异能，并在向量数据库中进行搜索
  4. 找到卡牌后，Deepseek会再次阅读卡片文本，按照相关度排序展示给用户。

## 界面设计

1. 要求界面和字体使用中世纪奇幻风格主题，同时保持简洁
2. 支持明暗主题切换
3. 在移动设备和桌面浏览器中均有较好的排版
4. 使用前后端分离设计，前端使用React或其他成熟的前端框架

## 其他

1. 后端使用langgraph或者langchain
2. DEEPSEEK_API_KEY="REDACTED-DEEPSEEK-KEY"


## 新增需求


1. 将原始数据从sqlite迁移到postgresql+JSONB中，数据库使用Docker部署，将数据挂载到容器中，原始数据中的以下字段将会得到被迁移：
```
id
name
lang
released_at
uri
scryfall_uri
layout
image_uris: {
  art_crop
  border_crop
}
mana_cost
cmc
type_line
oracle_text
power
toughness
colors
```
2. postgresql需要支持pgvector，并将以下字段的数据向量化存储，使用bge-largn-en，这个步骤你写一个脚本让我执行，不需要你执行
  
```
(RAG) name
(RAG) type_line
(RAG) oracle_text
```

1. 用户输入查询语句后
   1. 大模型优化查询语句得到优化后的查询语句A
   2. 大模型解析查询语句A中的条件（例如发布时间在2012年以后、法力值大于5），调用mcp工具从数据库中进行卡片的初步筛选，支持根据released_at、layout、mana_cost、cmc、power、toughness、colors生成查询语句，如果查询语句中没有相关的字段，那么就省略。对于MCP工具的输入参数，遵循以下法则：
      1. 对于不可穷举的参数，使用条件语句，例如对于power参数，可以输入 ">10"，对于released_at，可以输入表示“在xx日期之后”的逻辑表达式
      2. 对于可穷举的参数，可以使用精准匹配，例如对于colors参数，可以输入 “B R”，MCP工具查询colors中包括Blue和Red的卡片，在例如layout参数，可以指定是否为双面牌
   3. 大模型根据查询语句A，去向量化搜索相关的ability（例如Lifelink）
   4. 大模型根据查询语句A和步骤3中得到的ability，准备向量化查询语句：
      1. 如果查询语句A中指定了卡片名，那么将其作为name向量化查询语句
      2. 如果查询语句A中指定了卡片类型，那么将其作为type_line向量化查询语句
      3. 如果查询语句A中指定了卡片效果，那么将其与ability拼接起来作为oracle_text向量化查询语句
   5. 从卡片数据库中向量化搜索name、type_line、oracle_text，将结果根据RRF (Reciprocal Rank Fusion)算法进行排名

