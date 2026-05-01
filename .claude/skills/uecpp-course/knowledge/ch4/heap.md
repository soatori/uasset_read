# TArray 堆操作

TArray 内置了将数组转换为**二叉堆**的操作。默认是**最小堆**（堆顶元素最小）。

## 堆结构

```
二叉堆（最小堆）：
        0 (最小)
       / \
      1   2
     / \  / \
    3  4 5   6
```

- 根节点在索引 0
- 左子节点在 `2n + 1`
- 右子节点在 `2n + 2`
- 兄弟节点之间没有特定顺序
- 父节点总是小于（或等于）子节点

## Heapify()

```cpp
TArray<int32> Arr = {5, 3, 1, 4, 2};
Arr.Heapify();  // 转换为最小堆：{1, 2, 3, 4, 5}
```

将普通数组转换为堆结构，使用 `operator<` 比较。

## HeapPush()

```cpp
Arr.HeapPush(0);  // 将 0 插入堆并维护堆结构：{0, 1, 3, 4, 2, 5}
```

添加新元素到堆中并调整位置以维持堆性质。

## HeapPop()

```cpp
int32 TopElement;
Arr.HeapPop(TopElement);  // TopElement = 1（堆顶），Arr 移除堆顶并维护堆结构
```

移除堆顶元素，通过引用参数输出被移除的元素。堆结构自动维护。

## HeapRemoveTop()

```cpp
Arr.HeapRemoveTop();  // 仅移除堆顶元素，不输出
```

与 `HeapPop` 的区别：不返回被移除的元素。

## HeapTop()

```cpp
int32 Top = HeapArr.HeapTop();  // 只读查看堆顶元素，不移除
```

区别于 `HeapPop()`：`HeapTop()` 只查看不修改数组，`HeapPop()` 移除堆顶并输出。

## HeapRemoveAt()

```cpp
Arr.HeapRemoveAt(Index);  // 移除指定索引的元素并维护堆结构
```

## 应用场景

- 数据结构：需要频繁获取最小/最大元素的数据管理
- 资源加载优先级队列
- 游戏定时器管理
- Boss 刷新时间调度

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGHeapArray()`
