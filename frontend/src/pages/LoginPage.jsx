import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";

function LoginPage() {
  const [tab, setTab] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Verification state
  const [showVerification, setShowVerification] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const [resending, setResending] = useState(false);

  const { login, register, verifyEmail, resendVerification } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    if (tab === "register" && password !== confirmPassword) {
      showToast("两次输入的密码不一致", "error");
      return;
    }
    if (tab === "register" && password.length < 6) {
      showToast("密码至少需要6个字符", "error");
      return;
    }
    if (tab === "register" && !email.trim()) {
      showToast("请输入邮箱地址", "error");
      return;
    }
    setSubmitting(true);
    try {
      if (tab === "login") {
        const user = await login(username.trim(), password);
        // 只对绑定了邮箱的账号强制验证；无邮箱的旧账号跳过，否则会陷入
        // "要求验证 → 但没有邮箱可收码" 的死循环。
        if (user.email_verified === false && user.email) {
          setEmail(user.email || "");
          // Resend a fresh code since the old one may have expired
          try { await resendVerification(); } catch {}
          setShowVerification(true);
          showToast("请先验证邮箱，验证码已发送");
        } else {
          showToast("登录成功");
          navigate("/");
        }
      } else {
        await register(username.trim(), password, email.trim());
        showToast("注册成功，验证码已发送到邮箱");
        setShowVerification(true);
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!verificationCode.trim()) return;
    setSubmitting(true);
    try {
      await verifyEmail(verificationCode.trim());
      showToast("邮箱验证成功");
      navigate("/");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResend = async () => {
    setResending(true);
    try {
      await resendVerification();
      showToast("验证码已重新发送");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setResending(false);
    }
  };

  if (showVerification) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h2 className="login-title">验证邮箱</h2>
          <p className="verify-hint">
            验证码已发送至 <strong>{email || "你的邮箱"}</strong>，请查收并输入 6 位验证码。
          </p>
          <form onSubmit={handleVerify} className="login-form">
            <div className="form-group">
              <label htmlFor="verification-code">验证码</label>
              <input
                id="verification-code"
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
                placeholder="输入 6 位验证码"
                autoComplete="one-time-code"
                disabled={submitting}
                className="verify-code-input"
              />
            </div>
            <button type="submit" className="login-submit" disabled={submitting || verificationCode.length !== 6}>
              {submitting ? "验证中..." : "确认验证"}
            </button>
          </form>
          <div className="verify-actions">
            <button
              className="verify-resend"
              onClick={handleResend}
              disabled={resending}
            >
              {resending ? "发送中..." : "重新发送验证码"}
            </button>
          </div>
        </div>
      </div>
    );
  }

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
          {tab === "register" && (
            <div className="form-group">
              <label htmlFor="email">邮箱</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="输入邮箱地址"
                autoComplete="email"
                disabled={submitting}
              />
            </div>
          )}
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
