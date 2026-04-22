import { useEffect, useState } from "react";
import { fetchAdminSettings, updateAdminSettings } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";

export default function SettingsSection() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [anonLimit, setAnonLimit] = useState("");
  const [userLimit, setUserLimit] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    fetchAdminSettings()
      .then((res) => res.json())
      .then((data) => {
        setSettings(data);
        setAnonLimit(String(data.anon_hourly_limit));
        setUserLimit(String(data.user_hourly_limit));
      })
      .catch(() => showToast("加载设置失败", "error"))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    const anon = parseInt(anonLimit, 10);
    const user = parseInt(userLimit, 10);
    if (isNaN(anon) || anon < 0 || isNaN(user) || user < 0) {
      showToast("请输入有效的非负整数", "error");
      return;
    }
    setSaving(true);
    try {
      const res = await updateAdminSettings({ anon_hourly_limit: anon, user_hourly_limit: user });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        showToast("设置已保存");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "保存失败", "error");
      }
    } catch {
      showToast("保存失败", "error");
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
      <h2 className="admin-title">系统设置</h2>

      <div className="admin-settings-card">
        <h3 className="admin-settings-card-title">搜索频率限制</h3>
        <p className="admin-db-card-desc">
          限制用户每小时的 AI 搜索次数。管理员不受此限制。设置为 0 表示禁止搜索。
        </p>

        <div className="admin-settings-form">
          <div className="admin-settings-field">
            <label className="admin-settings-label">匿名用户（每小时）</label>
            <div className="admin-settings-input-row">
              <input
                type="number"
                className="admin-settings-input"
                value={anonLimit}
                onChange={(e) => setAnonLimit(e.target.value)}
                min="0"
                step="1"
              />
              <span className="admin-settings-unit">次/小时</span>
            </div>
            <span className="admin-settings-hint">按 IP 地址限制未登录用户的搜索频率</span>
          </div>

          <div className="admin-settings-field">
            <label className="admin-settings-label">注册用户（每小时）</label>
            <div className="admin-settings-input-row">
              <input
                type="number"
                className="admin-settings-input"
                value={userLimit}
                onChange={(e) => setUserLimit(e.target.value)}
                min="0"
                step="1"
              />
              <span className="admin-settings-unit">次/小时</span>
            </div>
            <span className="admin-settings-hint">按用户账号限制已登录用户的搜索频率</span>
          </div>
        </div>

        <div className="admin-settings-actions">
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || !hasChanges}
          >
            {saving ? "保存中..." : "保存设置"}
          </button>
        </div>
      </div>
    </>
  );
}
