-- Purpose: Seed MVP/demo users and assign roles.
-- Related: ../init.sql, backend/app/routers/auth.py.
-- Notes: Intended for local/dev/MVP bootstrap. Do not run in production unless explicitly desired.
-- ============================================

INSERT INTO users (id, username, password_hash, full_name, institution, is_active, is_verified) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'admin',
     '$2b$12$ykVyCPCS1jq1QIVsMIlJAOI1gDWuQjRmazwyNkEZTVyx7gNW8kiK.',
     '系统管理员', '念通软件', TRUE, TRUE)
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    is_active = TRUE,
    is_verified = TRUE,
    updated_at = NOW();

INSERT INTO users (id, username, password_hash, full_name, institution, is_active, is_verified) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'user1',
     '$2b$12$ykVyCPCS1jq1QIVsMIlJAOI1gDWuQjRmazwyNkEZTVyx7gNW8kiK.',
     '张三', '某医院', TRUE, TRUE)
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    is_active = TRUE,
    is_verified = TRUE,
    updated_at = NOW();

INSERT INTO users (id, username, password_hash, full_name, institution, is_active, is_verified) VALUES
    ('550e8400-e29b-41d4-a716-446655440002', 'user2',
     '$2b$12$ykVyCPCS1jq1QIVsMIlJAOI1gDWuQjRmazwyNkEZTVyx7gNW8kiK.',
     '李四', '某大学', TRUE, TRUE)
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    is_active = TRUE,
    is_verified = TRUE,
    updated_at = NOW();

-- ============================================
-- 8. 用户-角色分配
-- ============================================

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.username = 'admin' AND r.code = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.username = 'user1' AND r.code = 'pi'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.username = 'user2' AND r.code = 'pi'
ON CONFLICT DO NOTHING;
