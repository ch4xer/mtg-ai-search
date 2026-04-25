export default function ImportNotFoundBanner({ importNotFound, language, onClose }) {
  if (importNotFound.length === 0) return null;

  return (
    <div className="import-not-found">
      <div className="import-not-found-header">
        <span>
          {language === "zh"
            ? `以下 ${importNotFound.length} 张卡牌未在数据库中找到：`
            : `The following ${importNotFound.length} cards were not found in the database:`}
        </span>
        <button className="import-not-found-close" onClick={onClose}>&times;</button>
      </div>
      <ul>
        {importNotFound.map((name, index) => (
          <li key={`${name}-${index}`}>
            <a
              className="import-not-found-link"
              href={`https://scryfall.com/search?q=${encodeURIComponent(name)}`}
              target="_blank"
              rel="noopener noreferrer"
              title={language === "zh" ? "在 Scryfall 中搜索" : "Search on Scryfall"}
            >
              {name}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
