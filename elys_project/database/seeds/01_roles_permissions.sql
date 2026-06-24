-- Purpose: Seed system roles, permissions, and role-permission mappings.
-- Related: ../init.sql, backend/app/models/role.py, backend/app/models/user.py.
-- Notes: Does not create demo users. Use 02_dev_users.sql only for MVP/dev environments.
-- ============================================

INSERT INTO roles (code, name, name_en, description, is_system) VALUES
    ('superadmin', '超级管理员', 'Super Admin', '平台治理与管理员管理（管理员的管理者），独立于数据集生命周期', TRUE),
    ('admin',     '管理员',    'Admin',       '系统管理员，拥有全部权限', TRUE),
    ('pi',        'PI',        'Principal Investigator', '可创建研究项，也可作为成员参与其他研究项', TRUE)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    name_en = EXCLUDED.name_en,
    description = EXCLUDED.description,
    is_system = TRUE;

INSERT INTO user_roles (user_id, role_id)
SELECT DISTINCT ur.user_id, pi_role.id
FROM user_roles ur
JOIN roles old_role ON old_role.id = ur.role_id
JOIN roles pi_role ON pi_role.code = 'pi'
WHERE old_role.code IN ('researcher', 'reviewer')
ON CONFLICT DO NOTHING;

DELETE FROM user_roles
WHERE role_id IN (SELECT id FROM roles WHERE code IN ('researcher', 'reviewer'));

DELETE FROM role_permissions
WHERE role_id IN (SELECT id FROM roles WHERE code IN ('researcher', 'reviewer'));

DELETE FROM roles WHERE code IN ('researcher', 'reviewer');

-- ============================================
-- 5. 插入权限
-- ============================================

INSERT INTO permissions (code, name, description) VALUES
    ('user:read',   '查看用户',   '查看用户列表和信息'),
    ('user:write',  '管理用户',   '创建、编辑、删除用户'),
    ('study:read','查看研究项', '查看研究项详情和数据'),
    ('study:write','编辑研究项', '创建和编辑研究项'),
    ('study:delete','删除研究项', '删除研究项'),
    ('data:read',   '查看数据',   '浏览和下载数据'),
    ('data:write',  '管理数据',   '上传和编辑数据'),
    ('pipeline:read','查看工作流','查看分析工作流'),
    ('pipeline:write','编辑工作流','创建和编辑工作流'),
    ('chart:read',  '查看图表',   '查看分析图表'),
    ('chart:write', '编辑图表',   '创建和编辑图表'),
    ('chart:export','导出图表',   '导出图表为文件'),
    ('stats:read',  '查看统计',   '查看统计分析'),
    ('stats:write', '管理统计',   '创建和编辑统计分析'),
    ('ml:read',     '查看ML',     '查看机器学习模型'),
    ('ml:write',    '管理ML',     '创建和编辑ML模型'),
    ('task:read',   '查看任务',   '查看任务状态'),
    ('task:write',  '管理任务',   '创建和管理任务'),
    ('admin:read',  '查看管理',   '查看管理面板'),
    ('admin:write', '系统管理',   '系统配置和审计')
ON CONFLICT (code) DO NOTHING;

-- ============================================
-- 6. 角色-权限分配
-- ============================================

DELETE FROM role_permissions
WHERE role_id IN (SELECT id FROM roles WHERE code IN ('superadmin', 'admin', 'pi'));

-- superadmin: 平台治理与管理员管理，授予全部权限（管理员之上的超级角色，与数据集生命周期无关）
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'superadmin'
ON CONFLICT DO NOTHING;

-- admin: 全部权限
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'admin'
ON CONFLICT DO NOTHING;

-- pi: 可创建研究项，并在自己拥有或被授权的研究项中进行数据和分析工作
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'pi' AND p.code IN (
    'user:read', 'study:read', 'study:write',
    'data:read', 'data:write',
    'pipeline:read', 'pipeline:write',
    'chart:read', 'chart:write', 'chart:export',
    'stats:read', 'stats:write',
    'ml:read', 'ml:write',
    'task:read', 'task:write'
)
ON CONFLICT DO NOTHING;
