import { useLanguage } from "../contexts/LanguageContext.jsx";

function Footer() {
  const { t } = useLanguage();

  return (
    <footer className="footer">
      <div className="footer-inner">
        <p>{t('footerText')}</p>
      </div>
    </footer>
  );
}

export default Footer;
