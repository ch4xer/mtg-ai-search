// Translation strings for the application
export const translations = {
  en: {
    // Header
    appTitle: "MTG Card Search",

    // Navigation
    aiSearch: "AI Search",
    exactMatch: "Exact Match",
    decks: "Decks",
    admin: "Admin",
    login: "Login",
    logout: "Logout",

    // Search modes
    searchPlaceholder: "Describe the card you want to find...",
    searchPlaceholderDiscover: "Search name, type, text...",
    searchButton: "Search",
    searching: "Searching...",

    // Filters
    filters: "Filters",
    hideFilters: "Hide Filters",
    colors: "Colors",
    type: "Type",
    subtype: "Subtype",
    rarity: "Rarity",
    any: "Any",
    cmc: "CMC",
    power: "Power",
    toughness: "Toughness",
    abilities: "Abilities",
    addAbility: "Add...",
    playtest: "Playtest",
    clearAll: "Clear All",

    // Rarity options
    common: "Common",
    uncommon: "Uncommon",
    rare: "Rare",
    mythic: "Mythic",

    // Results
    noCardsFound: "No cards found matching your filters",
    noCardsFoundAI: "No cards found, try a different description",

    // Pagination
    previous: "Previous",
    next: "Next",

    // Features
    featureAiSearch: "AI Smart Search",
    featureAiSearchDesc: "Describe the card you want in natural language. AI will understand your intent and find the most matching results, supporting both Chinese and English queries.",
    featureDeckManagement: "Deck Management",
    featureDeckManagementDesc: "Create and manage your decks, add cards from search results with one click, support browsing by type and deck list import/export.",
    featurePdfExport: "Printable PDF Export",
    featurePdfExportDesc: "Export decks as A4 size PDF files, 9 cards per page in 3×3 layout, using high-quality card images, convenient for printing proxies.",

    // Theme
    switchTheme: "Switch theme",
    switchToArtMode: "Switch to art mode",
    switchToCardMode: "Switch to card mode",

    // Deck page
    myDecks: "My Decks",
    createDeck: "Create Deck",
    deckName: "Deck Name",
    deckFormat: "Format",
    mainboard: "Mainboard",
    sideboard: "Sideboard",
    exportDeck: "Export",
    exportPdf: "Export PDF",
    exportImages: "Export Images",
    importDeck: "Import",
    deckEmpty: "Deck is empty, go search page to add cards",
    backToDecks: "Back to deck list",
    clickToRename: "Click to rename",
    switchFormat: "Switch format",
    cardsCount: "cards",
    mainboardCards: "mainboard",
    sideboardCards: "sideboard",
    importDecklist: "Import decklist",
    copyDecklist: "Copy decklist",
    deleteDeck: "Delete deck",
    deckNotFound: "Deck not found",
    loadFailed: "Load failed",
    loadingDeck: "Loading deck...",
    downloadProgress: "Downloading card images",
    generatingPdf: "Generating PDF...",
    generatingZip: "Generating ZIP...",
    exportSuccess: "PDF exported successfully",
    exportImagesSuccess: "Images exported successfully",
    exportFailed: "Export failed",
    cardRemoved: "Card removed",
    deckRenamed: "Deck renamed",
    formatChanged: "Format changed",
    deckDeleted: "Deck deleted",
    cardsImported: "cards imported",
    cardsNotFound: "cards not found",
    decklistCopied: "Decklist copied to clipboard",
    copyFailed: "Copy failed",
    cardsNotInDb: "cards not found in database",
    clickCardDetails: "Click a card to view details",
    cardTypes: "Card Types",
    colorDistribution: "Color Distribution",
    manaCurve: "Mana Curve",
    rarityDistribution: "Rarity Distribution",
    cardIllegalInFormat: "Card illegal in this format",
    importPlaceholder: "Paste decklist text, each line: quantity card name\nExample:\n4 Lightning Bolt\n4 Counterspell\n\nSIDEBOARD\n2 Negate\n1 Pyroblast",
    cancel: "Cancel",
    confirm: "Confirm",

    // Auth
    username: "Username",
    password: "Password",
    email: "Email",
    register: "Register",
    registering: "Registering...",
    loggingIn: "Logging in...",

    // Errors
    searchLimitReached: "Search limit reached",
    searchLimitReachedAnon: "Anonymous search limit reached, please login",

    // Image mode
    artCrop: "Art Crop",
    borderCrop: "Full Card",
  },

  zh: {
    // Header
    appTitle: "MTG 卡牌搜索",

    // Navigation
    aiSearch: "AI 搜索",
    exactMatch: "精准匹配",
    decks: "卡组",
    admin: "管理",
    login: "登录",
    logout: "退出",

    // Search modes
    searchPlaceholder: "能让对手弃牌的黑色生物",
    searchPlaceholderDiscover: "搜索名称、类型、文本...",
    searchButton: "搜索",
    searching: "搜索中...",

    // Filters
    filters: "过滤器",
    hideFilters: "隐藏过滤器",
    colors: "颜色",
    type: "类型",
    subtype: "子类型",
    rarity: "稀有度",
    any: "任意",
    cmc: "法术力值",
    power: "力量",
    toughness: "防御",
    abilities: "能力",
    addAbility: "添加...",
    playtest: "测试卡",
    clearAll: "清除全部",

    // Rarity options
    common: "普通",
    uncommon: "非普通",
    rare: "稀有",
    mythic: "秘稀",

    // Results
    noCardsFound: "没有找到符合条件的卡牌",
    noCardsFoundAI: "没有找到卡牌，请尝试不同的描述",

    // Pagination
    previous: "上一页",
    next: "下一页",

    // Features
    featureAiSearch: "AI 智能搜索",
    featureAiSearchDesc: "用自然语言描述你想要的卡牌，AI 会理解你的意图并找到最匹配的结果，支持中英文混合查询。",
    featureDeckManagement: "卡组管理",
    featureDeckManagementDesc: "创建并管理你的卡组，在搜索结果中一键添加卡牌，支持按类型分组浏览和牌表导入导出。",
    featurePdfExport: "导出可打印 PDF",
    featurePdfExportDesc: "将卡组导出为 A4 尺寸的 PDF 文件，每页 9 张卡牌按 3×3 排列，使用高清卡图，方便打印代牌。",

    // Theme
    switchTheme: "切换主题",
    switchToArtMode: "切换为画作模式",
    switchToCardMode: "切换为卡牌模式",

    // Deck page
    myDecks: "我的卡组",
    createDeck: "创建卡组",
    deckName: "卡组名称",
    deckFormat: "赛制",
    mainboard: "主牌组",
    sideboard: "备牌",
    exportDeck: "导出",
    exportPdf: "导出 PDF",
    exportImages: "导出图集",
    importDeck: "导入",
    deckEmpty: "卡组为空，去搜索页面添加卡牌吧",
    backToDecks: "返回卡组列表",
    clickToRename: "点击重命名",
    switchFormat: "切换赛制",
    cardsCount: "张卡牌",
    mainboardCards: "主牌",
    sideboardCards: "备牌",
    importDecklist: "导入牌表",
    copyDecklist: "复制牌表",
    deleteDeck: "删除卡组",
    deckNotFound: "卡组不存在",
    loadFailed: "加载失败",
    loadingDeck: "加载卡组中...",
    downloadProgress: "下载卡牌图片",
    generatingPdf: "生成 PDF...",
    generatingZip: "生成 ZIP...",
    exportSuccess: "PDF 导出成功",
    exportImagesSuccess: "图集导出成功",
    exportFailed: "导出失败",
    cardRemoved: "已移除卡牌",
    deckRenamed: "卡组已重命名",
    formatChanged: "赛制已切换",
    deckDeleted: "卡组已删除",
    cardsImported: "张卡牌已导入",
    cardsNotFound: "张卡牌未找到",
    decklistCopied: "牌表已复制到剪贴板",
    copyFailed: "复制失败",
    cardsNotInDb: "张卡牌未在数据库中找到",
    clickCardDetails: "点击卡牌查看详情",
    cardTypes: "卡牌类型",
    colorDistribution: "颜色分布",
    manaCurve: "法术力曲线",
    rarityDistribution: "稀有度分布",
    cardIllegalInFormat: "该卡牌在此赛制中不合法",
    importPlaceholder: "粘贴牌表文本，每行格式：数量 卡牌名称\n例如：\n4 Lightning Bolt\n4 Counterspell\n\nSIDEBOARD\n2 Negate\n1 Pyroblast",
    cancel: "取消",
    confirm: "确定",

    // Auth
    username: "用户名",
    password: "密码",
    email: "邮箱",
    register: "注册",
    registering: "注册中...",
    loggingIn: "登录中...",

    // Errors
    searchLimitReached: "搜索次数已达上限",
    searchLimitReachedAnon: "未登录用户搜索次数已达上限，请登录后使用",

    // Image mode
    artCrop: "画作裁切",
    borderCrop: "完整卡牌",
  }
};

// Get browser language
export function getBrowserLanguage() {
  const lang = navigator.language || navigator.userLanguage;
  // Return 'zh' for Chinese variants, 'en' for everything else
  if (lang.startsWith('zh')) {
    return 'zh';
  }
  return 'en';
}

// Default language based on browser
export const defaultLanguage = getBrowserLanguage();