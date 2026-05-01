# GameplayTag 的四种创建方式

GameplayTag **不可在运行时动态创建**，必须在打包前通过以下四种方式之一注册。

## 方式一：Project Settings UI

路径：**Project Settings → GameplayTags**

- 手动添加标签名称和注释
- 适合快速原型测试和小项目
- 不适合团队协作（不便于版本控制）

## 方式二：INI 配置文件

路径：`Config/Tags/<文件名>.ini`

- 每个团队成员或子系统可维护独立文件
- 示例分工：
  - `XG_3C.ini` — 角色控制器标签
  - `XG_Mail.ini` — 邮件系统标签
  - `XG_Inventory.ini` — 背包系统标签
- 便于版本控制，适合团队协作

## 方式三：Data Table

使用 `DT_GameplayTagTable` 数据类型

- 适合非程序员管理标签（策划通过表格配置）
- 外部工具友好，Excel 编辑后导入
- 适合需要频繁增删标签的大型项目

## 方式四：C++ 宏声明（最推荐）

采用类似 `UE_LOG` 的声明模式，分为头文件和实现文件两部分。

详见 [GameplayTag 的 C++ 声明与使用](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/knowledge/ch11/04-GameplayTag的C++声明与使用.md)。

## 约束条件

- 所有标签必须在 **打包前** 完成注册
- 运行时不支持 `AddTag("Dynamic.New.Tag")` 等方式动态创建
- 空标签/默认标签的匹配操作始终返回 `false`
