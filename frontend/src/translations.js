// Translation strings for the application
export const translations = {
  en: {
    // Header
    appTitle: "MTG AI Search",

    // Navigation
    aiSearch: "AI Search",
    exactMatch: "Exact Match",
    decks: "Decks",
    settings: "Settings",
    admin: "Admin",
    login: "Login",
    logout: "Logout",

    // Search modes
    searchPlaceholder: "A black creature that makes opponents discard",
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
    backToHome: "Back to home",
    share: "Share",
    shareLinkCopied: "Share link copied to clipboard",
    noAnalysisYet: "No AI analysis yet",
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
    analyzeDeck: "Analyze Deck",
    reanalyzeDeck: "Re-analyze",
    analyzing: "Analyzing…",
    analysisFailed: "Analysis failed, please try again",
    analysisEmptyDeck: "Add cards to the deck before analyzing",
    analysisPlaystyle: "Playstyle",
    analysisWeaknesses: "Weaknesses",
    analysisDeckChanged: "Deck has changed since this analysis",
    analysisLastUpdated: "Last analyzed",
    justNow: "just now",
    minutesAgo: "{n} min ago",
    hoursAgo: "{n} h ago",
    daysAgo: "{n} d ago",
    cardIllegalInFormat: "Card illegal in this format",
    importPlaceholder: "Paste decklist text. Each line: quantity card name [(SET) collector_number]\nExamples:\n4 Lightning Bolt\n1 The Ur-Dragon (SLD) 11 *F*\n1 Sol Ring (SLD) 1494★\n\nSIDEBOARD\n2 Negate\n1 Pyroblast",
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

    // Settings page
    settingsTitle: "Account Settings",
    accountInfo: "Account Information",
    usernameLabel: "Username",
    emailLabel: "Email",
    roleLabel: "Role",
    emailNotSet: "Not set",
    emailVerified: "Verified",
    emailNotVerified: "Not verified",
    changePassword: "Change Password",
    changePasswordHint: "Changing your password requires email verification. Click the button below to send a verification code to your registered email.",
    sendCode: "Send Code",
    sending: "Sending...",
    codeSentTo: "Verification code sent to",
    enterCodeAndPassword: "Please enter the verification code and your new password.",
    verificationCode: "Verification Code",
    verificationCodePlaceholder: "Enter 6-digit code",
    newPassword: "New Password",
    newPasswordPlaceholder: "Enter new password (at least 6 characters)",
    confirmPassword: "Confirm Password",
    confirmPasswordPlaceholder: "Enter password again",
    confirmChange: "Confirm Change",
    changing: "Changing...",
    resendCode: "Resend Code",
    noEmailBound: "Your account has no email bound, cannot change password.",
    passwordMinLength: "Password must be at least 6 characters",
    passwordMismatch: "Passwords do not match",
    codeSentSuccess: "Verification code sent to your email",
    passwordChangedSuccess: "Password changed successfully",
    sendCodeFailed: "Failed to send verification code",
    changePasswordFailed: "Failed to change password",

    // Image mode
    artCrop: "Art Crop",
    borderCrop: "Full Card",

    // Art picker (deck)
    changeArt: "Change art",
    selectArtVersion: "Select art version",
    resetDefaultArt: "Reset",
    loadingVersions: "Loading...",
    fetchVersionsFailed: "Failed to fetch versions",
    artChanged: "Card art updated",
    artResetSuccess: "Card art reset to default",
    artChangeFailed: "Failed to update card art",

    // Footer
    footerText: "Unofficial Fan Content — not approved or endorsed by Wizards of the Coast. Card images and data © Wizards of the Coast. Card data provided by Scryfall (CC0).",
  },

  zh: {
    // Header
    appTitle: "MTG AI Search",

    // Navigation
    aiSearch: "AI 搜索",
    exactMatch: "精准匹配",
    decks: "卡组",
    settings: "设置",
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
    backToHome: "返回首页",
    share: "分享",
    shareLinkCopied: "分享链接已复制到剪贴板",
    noAnalysisYet: "暂无 AI 分析报告",
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
    analyzeDeck: "分析卡组",
    reanalyzeDeck: "重新分析",
    analyzing: "分析中…",
    analysisFailed: "分析失败，请稍后重试",
    analysisEmptyDeck: "请先添加卡牌再进行分析",
    analysisPlaystyle: "对战思路",
    analysisWeaknesses: "主要弱点",
    analysisDeckChanged: "卡组自上次分析以来有改动",
    analysisLastUpdated: "最近分析于",
    justNow: "刚刚",
    minutesAgo: "{n} 分钟前",
    hoursAgo: "{n} 小时前",
    daysAgo: "{n} 天前",
    cardIllegalInFormat: "该卡牌在此赛制中不合法",
    importPlaceholder: "粘贴牌表文本，每行格式：数量 卡牌名称 [(系列代码) 收藏编号]\n例如：\n4 Lightning Bolt\n1 The Ur-Dragon (SLD) 11 *F*\n1 Sol Ring (SLD) 1494★\n\nSIDEBOARD\n2 Negate\n1 Pyroblast",
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

    // Settings page
    settingsTitle: "账号设置",
    accountInfo: "账号信息",
    usernameLabel: "用户名",
    emailLabel: "邮箱",
    roleLabel: "角色",
    emailNotSet: "未设置",
    emailVerified: "已验证",
    emailNotVerified: "未验证",
    changePassword: "修改密码",
    changePasswordHint: "修改密码需要通过邮箱验证。点击下方按钮，验证码将发送到你的注册邮箱。",
    sendCode: "发送验证码",
    sending: "发送中...",
    codeSentTo: "验证码已发送至",
    enterCodeAndPassword: "请输入验证码和新密码。",
    verificationCode: "验证码",
    verificationCodePlaceholder: "输入 6 位验证码",
    newPassword: "新密码",
    newPasswordPlaceholder: "输入新密码（至少 6 位）",
    confirmPassword: "确认密码",
    confirmPasswordPlaceholder: "再次输入新密码",
    confirmChange: "确认修改",
    changing: "修改中...",
    resendCode: "重新发送验证码",
    noEmailBound: "你的账号未绑定邮箱，无法修改密码。",
    passwordMinLength: "密码至少需要6个字符",
    passwordMismatch: "两次输入的密码不一致",
    codeSentSuccess: "验证码已发送到你的邮箱",
    passwordChangedSuccess: "密码修改成功",
    sendCodeFailed: "发送验证码失败",
    changePasswordFailed: "密码修改失败",

    // Image mode
    artCrop: "画作裁切",
    borderCrop: "完整卡牌",

    // Art picker (deck)
    changeArt: "切换卡图",
    selectArtVersion: "选择卡图版本",
    resetDefaultArt: "恢复默认",
    loadingVersions: "加载中...",
    fetchVersionsFailed: "获取版本列表失败",
    artChanged: "卡图已更新",
    artResetSuccess: "卡图已恢复默认",
    artChangeFailed: "更新卡图失败",

    // Footer
    footerText: "非官方粉丝内容，未经威世智（Wizards of the Coast）批准或认可。卡牌图像及数据 © Wizards of the Coast。卡牌数据由 Scryfall 以 CC0 协议提供。",
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
