"""通用枚举值：内置=1、自定义=2。

用于 skill/agent/group 的 `type` 列，以及 manage 中 `roles.role_type`、
`permissions.permission_type`（与库表含义一致）。
"""

# 资源类型：内置=1、自定义=2。
RESOURCE_TYPE_BUILTIN = 1
RESOURCE_TYPE_CUSTOM = 2
