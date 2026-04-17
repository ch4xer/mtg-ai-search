import { useState } from "react";
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
    </div>
  );
}

export default SettingsPage;
