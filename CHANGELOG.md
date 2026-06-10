# Changelog

## [1.0.0] - 2026-06-10

### Fixed
- 修复批量转换页面不保存的严重 bug
- 修复 needs_conversion() 比较逻辑错误
- 修复移动页面前未检查目标页是否存在的 bug
- 修复子页面编辑失败跳过所有剩余子页面的问题
- 修复速率限制后不重试失败页面的问题

### Changed
- 预编译所有正则表达式提升性能
- 添加代码块/source/nowiki 标签保护
- 移除死代码（skip_fields, replace_in_page, batch_process_pages）
- 统一异常处理，使用 safe_error() 防止信息泄露
- 添加环境变量验证，缺少配置时给出清晰错误

### Added
- 添加 safe_error() 安全异常处理函数
- 添加 __version__ 版本号
- 添加 FandomBot.__repr__ 方便调试
- 补全所有公共方法的 docstring 和类型标注