# TSet 概述

## 容器特性

TSet 是 UE 提供的**基于哈希表的无序集合容器**。与 TMap 的核心区别在于：TSet 是**元素即键（element-as-key）** 的容器，元素本身同时扮演键的角色，不存在独立的键值分离。

| 特性 | 说明 |
|------|------|
| 底层结构 | 哈希表（hash table）+ 桶（bucket） |
| 元素顺序 | **不可靠、不稳定**。顺序由哈希值决定，插入/删除可能改变已有元素的相对顺序 |
| 元素即键 | 元素本身参与哈希计算，不区分键和值 |
| 同质容器 | 所有元素必须是同一类型 |
| 重复策略 | 默认不允许重复键，重复插入覆盖已有值 |
| 内存布局 | **非连续内存**，指针/引用在插入/删除后**可能失效** |
| 分配器 | 基于 Set Allocator 的桶式分配 |

## 与 TMap 的对比

| 维度 | TSet | TMap |
|------|------|------|
| 数据结构 | TSet\<ElementType\> | TMap\<KeyType, ValueType\> |
| 元素形式 | 单一类型（元素本身即键） | 键值对（TPair\<KeyType, ValueType\>） |
| 迭代返回值 | 元素引用（`FString&`） | TPair 引用（`TPair<K,V>&`） |
| 查找返回 | 元素指针（无独立键查找） | 值引用/指针（通过键查找值） |
| 常见操作模式 | 集合运算（并/交/差） | 字典/映射模式 |
| 使用频率 | 低于 TArray 和 TMap | 高于 TSet |

## 代码引用

- [SetActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.h)：类声明和 UPROPERTY 蓝图暴露
- [SetActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp)：所有操作实现
