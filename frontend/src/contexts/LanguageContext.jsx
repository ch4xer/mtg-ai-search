import { createContext, useContext, useState, useEffect } from 'react';
import { translations, getBrowserLanguage } from '../translations';

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(() => {
    // Check localStorage first, then browser language
    const saved = localStorage.getItem('mtg-language');
    if (saved && (saved === 'en' || saved === 'zh')) {
      return saved;
    }
    return getBrowserLanguage();
  });

  useEffect(() => {
    localStorage.setItem('mtg-language', language);
  }, [language]);

  const t = (key) => {
    const langStrings = translations[language] || translations.en;
    return langStrings[key] || key;
  };

  const toggleLanguage = () => {
    setLanguage(prev => prev === 'en' ? 'zh' : 'en');
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, toggleLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }
  return context;
}