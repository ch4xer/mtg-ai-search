import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";

function LoginPage() {
  const [tab, setTab] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    if (tab === "register" && password !== confirmPassword) {
      showToast("两次输入的密码不一致", "error");
      return;
    }
    if (tab === "register" && password.length < 4) {
      showToast("密码至少需要4个字符", "error");
      return;
    }
    setSubmitting(true);
    try {
      if (tab === "login") {
        await login(username.trim(), password);
        showToast("登录成功");
      } else {
        await register(username.trim(), password);
        showToast("注册成功");
      }
      navigate("/");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h2 className="login-title">
          {tab === "login" ? "欢迎回来" : "创建账号"}
        </h2>
        <div className="login-tabs">
          <button
            className={`login-tab ${tab === "login" ? "active" : ""}`}
            onClick={() => setTab("login")}
          >
            登录
          </button>
          <button
            className={`login-tab ${tab === "register" ? "active" : ""}`}
            onClick={() => setTab("register")}
          >
            注册
          </button>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="输入用户名"
              autoComplete="username"
              disabled={submitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="输入密码"
              autoComplete={tab === "login" ? "current-password" : "new-password"}
              disabled={submitting}
            />
          </div>
          {tab === "register" && (
            <div className="form-group">
              <label htmlFor="confirm-password">确认密码</label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="再次输入密码"
                autoComplete="new-password"
                disabled={submitting}
              />
            </div>
          )}
          <button type="submit" className="login-submit" disabled={submitting}>
            {submitting ? "请稍候..." : tab === "login" ? "登录" : "注册"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
