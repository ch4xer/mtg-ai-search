import { useEffect, useState } from "react";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";

function SettingsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const { t, language } = useLanguage();

  // Password change flow
  const [step, setStep] = useState("idle"); // idle | code_sent | submitting
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [requesting, setRequesting] = useState(false);
  const [changing, setChanging] = useState(false);
  const [apiKeyStatus, setApiKeyStatus] = useState(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(true);
  const [apiKeyGenerating, setApiKeyGenerating] = useState(false);
  const [generatedApiKey, setGeneratedApiKey] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadApiKeyStatus = async () => {
      setApiKeyLoading(true);
      try {
        const res = await apiFetch("/api/auth/api-key");
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setApiKeyStatus(data);
      } finally {
        if (!cancelled) setApiKeyLoading(false);
      }
    };

    loadApiKeyStatus();
    return () => { cancelled = true; };
  }, []);

  const handleRequestCode = async () => {
    setRequesting(true);
    try {
      const res = await apiFetch("/api/auth/request-password-change", { method: "POST" });
      if (res.ok) {
        setStep("code_sent");
        showToast(t('codeSentSuccess'));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('sendCodeFailed'), "error");
      }
    } catch {
      showToast(t('sendCodeFailed'), "error");
    } finally {
      setRequesting(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      showToast(t('passwordMinLength'), "error");
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast(t('passwordMismatch'), "error");
      return;
    }
    setChanging(true);
    try {
      const res = await apiFetch("/api/auth/change-password", {
        method: "POST",
        body: { code: code.trim(), new_password: newPassword },
      });
      if (res.ok) {
        showToast(t('passwordChangedSuccess'));
        setStep("idle");
        setCode("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('changePasswordFailed'), "error");
      }
    } catch {
      showToast(t('changePasswordFailed'), "error");
    } finally {
      setChanging(false);
    }
  };

  const handleGenerateApiKey = async () => {
    if (apiKeyStatus?.has_api_key) {
      const confirmed = confirm(t('apiKeyRegenerateConfirm'));
      if (!confirmed) return;
    }

    setApiKeyGenerating(true);
    try {
      const res = await apiFetch("/api/auth/api-key", { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('apiKeyGenerateFailed'), "error");
        return;
      }
      const data = await res.json();
      setGeneratedApiKey(data.api_key);
      setApiKeyStatus({ has_api_key: true, created_at: data.created_at });
      showToast(t('apiKeyGenerated'));
    } catch {
      showToast(t('apiKeyGenerateFailed'), "error");
    } finally {
      setApiKeyGenerating(false);
    }
  };

  const handleCopyApiKey = async () => {
    if (!generatedApiKey) return;
    try {
      await navigator.clipboard.writeText(generatedApiKey);
      showToast(t('apiKeyCopied'));
    } catch {
      showToast(generatedApiKey, "info");
    }
  };

  return (
    <div className="settings-page">
      <h2 className="settings-title">{t('settingsTitle')}</h2>

      <div className="settings-card">
        <h3 className="settings-section-title">{t('accountInfo')}</h3>
        <div className="settings-info-row">
          <span className="settings-label">{t('usernameLabel')}</span>
          <span className="settings-value">{user?.username}</span>
        </div>
        <div className="settings-info-row">
          <span className="settings-label">{t('emailLabel')}</span>
          <span className="settings-value">
            {user?.email || t('emailNotSet')}
            {user?.email_verified && <span className="settings-verified"> ({t('emailVerified')})</span>}
          </span>
        </div>
        <div className="settings-info-row">
          <span className="settings-label">{t('roleLabel')}</span>
          <span className="settings-value">{user?.role}</span>
        </div>
      </div>

      <div className="settings-card">
        <h3 className="settings-section-title">{t('changePassword')}</h3>
        {step === "idle" && (
          <div className="settings-password-idle">
            <p className="settings-hint">
              {t('changePasswordHint')}
            </p>
            <button
              className="btn-primary"
              onClick={handleRequestCode}
              disabled={requesting || !user?.email}
            >
              {requesting ? t('sending') : t('sendCode')}
            </button>
            {!user?.email && (
              <p className="settings-warning">{t('noEmailBound')}</p>
            )}
          </div>
        )}
        {step === "code_sent" && (
          <form onSubmit={handleChangePassword} className="settings-password-form">
            <p className="settings-hint">
              {t('codeSentTo')} <strong>{user?.email}</strong>，{t('enterCodeAndPassword')}
            </p>
            <div className="form-group">
              <label htmlFor="pw-code">{t('verificationCode')}</label>
              <input
                id="pw-code"
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder={t('verificationCodePlaceholder')}
                autoComplete="one-time-code"
                disabled={changing}
                className="verify-code-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="new-password">{t('newPassword')}</label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t('newPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={changing}
              />
            </div>
            <div className="form-group">
              <label htmlFor="confirm-new-password">{t('confirmPassword')}</label>
              <input
                id="confirm-new-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder={t('confirmPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={changing}
              />
            </div>
            <div className="settings-password-actions">
              <button
                type="submit"
                className="btn-primary"
                disabled={changing || code.length !== 6}
              >
                {changing ? t('changing') : t('confirmChange')}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleRequestCode}
                disabled={requesting}
              >
                {requesting ? t('sending') : t('resendCode')}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => { setStep("idle"); setCode(""); setNewPassword(""); setConfirmPassword(""); }}
              >
                {t('cancel')}
              </button>
            </div>
          </form>
        )}
      </div>

      <div className="settings-card">
        <h3 className="settings-section-title">{t('apiAccess')}</h3>
        <p className="settings-hint">{t('apiAccessHint')}</p>
        <div className="settings-info-row">
          <span className="settings-label">{t('apiKeyStatus')}</span>
          <span className="settings-value">
            {apiKeyLoading && t('loading')}
            {!apiKeyLoading && apiKeyStatus?.has_api_key && t('apiKeyExists')}
            {!apiKeyLoading && !apiKeyStatus?.has_api_key && t('apiKeyMissing')}
          </span>
        </div>
        {apiKeyStatus?.created_at && (
          <div className="settings-info-row">
            <span className="settings-label">{t('apiKeyCreatedAt')}</span>
            <span className="settings-value">{new Date(apiKeyStatus.created_at).toLocaleString()}</span>
          </div>
        )}
        {generatedApiKey && (
          <div className="settings-api-key-box">
            <p className="settings-warning">{t('apiKeyOneTime')}</p>
            <code>{generatedApiKey}</code>
            <button className="btn-secondary" type="button" onClick={handleCopyApiKey}>
              {t('copyApiKey')}
            </button>
          </div>
        )}
        <button
          className="btn-primary"
          type="button"
          onClick={handleGenerateApiKey}
          disabled={apiKeyGenerating}
        >
          {apiKeyGenerating && t('generating')}
          {!apiKeyGenerating && apiKeyStatus?.has_api_key && t('regenerateApiKey')}
          {!apiKeyGenerating && !apiKeyStatus?.has_api_key && t('generateApiKey')}
        </button>
      </div>
    </div>
  );
}

export default SettingsPage;
