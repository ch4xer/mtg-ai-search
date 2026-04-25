import { useEffect, useState } from "react";
import { fetchAdminSettings, updateAdminSettings } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";
import { useLanguage } from "../../../contexts/LanguageContext.jsx";

export default function SettingsSection() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [anonLimit, setAnonLimit] = useState("");
  const [userLimit, setUserLimit] = useState("");
  const { showToast } = useToast();
  const { t } = useLanguage();

  useEffect(() => {
    fetchAdminSettings()
      .then((res) => res.json())
      .then((data) => {
        setSettings(data);
        setAnonLimit(String(data.anon_hourly_limit));
        setUserLimit(String(data.user_hourly_limit));
      })
      .catch(() => showToast(t("adminSettingsLoadFailed"), "error"))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    const anon = parseInt(anonLimit, 10);
    const user = parseInt(userLimit, 10);
    if (isNaN(anon) || anon < 0 || isNaN(user) || user < 0) {
      showToast(t("adminSettingsInvalidInt"), "error");
      return;
    }
    setSaving(true);
    try {
      const res = await updateAdminSettings({ anon_hourly_limit: anon, user_hourly_limit: user });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        showToast(t("adminSettingsSaved"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("adminSettingsSaveFailed"), "error");
      }
    } catch {
      showToast(t("adminSettingsSaveFailed"), "error");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = settings && (
    String(settings.anon_hourly_limit) !== anonLimit ||
    String(settings.user_hourly_limit) !== userLimit
  );

  if (loading) return <div className="loading"><div className="loading-spinner" /></div>;

  return (
    <>
      <h2 className="admin-title">{t("adminTitleSettings")}</h2>

      <div className="admin-settings-card">
        <h3 className="admin-settings-card-title">{t("adminRateLimitTitle")}</h3>
        <p className="admin-db-card-desc">
          {t("adminRateLimitDesc")}
        </p>

        <div className="admin-settings-form">
          <div className="admin-settings-field">
            <label className="admin-settings-label">{t("adminRateLimitAnonLabel")}</label>
            <div className="admin-settings-input-row">
              <input
                type="number"
                className="admin-settings-input"
                value={anonLimit}
                onChange={(e) => setAnonLimit(e.target.value)}
                min="0"
                step="1"
              />
              <span className="admin-settings-unit">{t("adminRateLimitUnit")}</span>
            </div>
            <span className="admin-settings-hint">{t("adminRateLimitAnonHint")}</span>
          </div>

          <div className="admin-settings-field">
            <label className="admin-settings-label">{t("adminRateLimitUserLabel")}</label>
            <div className="admin-settings-input-row">
              <input
                type="number"
                className="admin-settings-input"
                value={userLimit}
                onChange={(e) => setUserLimit(e.target.value)}
                min="0"
                step="1"
              />
              <span className="admin-settings-unit">{t("adminRateLimitUnit")}</span>
            </div>
            <span className="admin-settings-hint">{t("adminRateLimitUserHint")}</span>
          </div>
        </div>

        <div className="admin-settings-actions">
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || !hasChanges}
          >
            {saving ? t("adminSettingsSaving") : t("adminSettingsSave")}
          </button>
        </div>
      </div>
    </>
  );
}
