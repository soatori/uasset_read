# 贡献者指南

## 开发环境

```bash
# 克隆仓库
git clone https://github.com/your-org/uasset_read.git
cd uasset_read

# 运行测试（无需 pip install -e .）
python -m pytest tests/ -v

# 运行单个测试
python -m pytest tests/test_properties.py::test_bool_property -v
```

## 项目结构

```
src/uasset_read/
├── archive.py          # FArchive 二进制读取器
├── parse_uasset.py     # 主解析管线
├── constants.py        # 所有常量
├── serializers/        # UE 结构序列化器
├── parsers/            # 属性解析器
├── graph/              # 蓝图图提取
├── kismet/             # Kismet 字节码反编译
├── link/               # PackageLinker 对象图
├── blueprint/          # 蓝图元数据提取
├── models/             # 数据模型
├── formatters/         # 输出格式化器
└── renderers/          # IR → 输出渲染
```

## 编码规范

- 所有文档、注释、错误信息使用中文
- 遵循 DRY、YAGNI、TDD
- 新增功能必须配套测试
- 类型注解优先使用具体类型，避免 Any

## 提交规范

```
feat: 添加新属性类型解析器
fix: 修复 FString 空指针问题
test: 添加 StructProperty 边界测试
docs: 更新 API 参考文档
refactor: 提取共享解析逻辑
chore: 更新版本号
```

## 测试要求

- ≥ 800 单元测试，100% 通过率
- ≥ 12 种资产类型覆盖
- 稳定资产在 strict 和 tolerant 双模式下通过
- 新增测试必须放在 `tests/` 对应子目录
