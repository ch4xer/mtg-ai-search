from .connection import get_pool

MAX_VERIFICATION_ATTEMPTS = 5


async def set_verification_code(user_id: str, code: str, expires_at) -> None:
    pool = await get_pool()
    await pool.execute(
        """UPDATE users SET verification_code = $1, verification_code_expires_at = $2,
                           verification_attempts = 0
           WHERE id = $3::uuid""",
        code,
        expires_at,
        user_id,
    )


async def verify_user_email(user_id: str, code: str) -> str:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT verification_attempts, verification_code, verification_code_expires_at FROM users WHERE id = $1::uuid",
        user_id,
    )
    if not row:
        return "invalid"
    if row["verification_attempts"] >= MAX_VERIFICATION_ATTEMPTS:
        return "too_many_attempts"

    await pool.execute(
        "UPDATE users SET verification_attempts = verification_attempts + 1 WHERE id = $1::uuid",
        user_id,
    )

    matched = await pool.fetchrow(
        """UPDATE users SET email_verified = TRUE, verification_code = NULL,
                           verification_code_expires_at = NULL, verification_attempts = 0
           WHERE id = $1::uuid AND verification_code = $2
             AND verification_code_expires_at > now()
           RETURNING id""",
        user_id,
        code,
    )
    return "ok" if matched else "invalid"
