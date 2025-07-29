# 版本控制建议方案

## 分支策略
1. `main` - 生产环境对应分支
2. `dev` - 集成开发分支
3. `feature/*` - 功能开发分支
4. `hotfix/*` - 紧急修复分支

## 提交信息模板
```
[类型]: [模块范围] 简明主题

• 类型: feat|fix|docs|style|refactor|test|chore
• 模块范围: signal|network|ui|core 等
• 主题: 50字符以内的简要描述

详细说明（可选）：
- 变更动机
- 实现细节
- 影响范围
```

## 代码规范检查
1. 提交前自动运行flake8检查
2. 类型注解覆盖率需≥85%
3. 单元测试覆盖率需≥70%

## 版本发布流程
1. 使用semantic-release自动生成版本号
2. CHANGELOG自动生成
3. 版本标签格式：v<major>.<minor>.<patch>