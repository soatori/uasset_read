# 材质资产 (UMaterial)

## 概述

UMaterial 类继承自 UMaterialInterface，定义材质的核心渲染属性和使用标志。核心用途：控制材质的渲染行为（混合模式、着色模型等）以及材质可应用于哪些几何类型。

参数系统和 Expression 引用不在本文档范围（per D-05）。

## 字段表

### 渲染属性字段

| 字段名 | 类型 | 访问 | 用途 |
|--------|------|------|------|
| MaterialDomain | TEnumAsByte\<EMaterialDomain\> | public | 材质域（Surface/PostProcess/Decal等），决定材质用途 |
| BlendMode | TEnumAsByte\<EBlendMode\> | public | 混合模式，控制透明度渲染方式（per D-14，不列出类型值） |
| ShadingModel | TEnumAsByte\<EMaterialShadingModel\> | **private** | 着色模型，通过 SetShadingModel() 设置（per D-13，不列出类型值） |
| ShadingModels | FMaterialShadingModelField | **private** | 多着色模型组合，支持同一材质使用多种着色（UE4.25+） |
| OpacityMaskClipValue | float | public | Masked 模式裁剪阈值（默认0.333） |
| TwoSided | uint8:1 | public | 双面材质，背面法线翻转 |
| bIsThinSurface | uint8:1 | public | 薄表面材质（Substrate专用，UE5） |
| bCastDynamicShadowAsMasked | uint8:1 | public | 半透明材质以遮罩模式投射动态阴影 |
| bFullyRough | uint8:1 | public | 强制完全粗糙，节省指令和一个采样器 |
| bTangentSpaceNormal | uint8:1 | public | 切线空间法线输入（需额外指令但更方便） |
| bUseMaterialAttributes | uint8:1 | public | 使用材质属性 Pin |
| bAllowNegativeEmissiveColor | uint8:1 | public | 允许负值自发光颜色（仅 Unlit 材质） |
| bHasPixelAnimation | uint8:1 | public | 像素动画标记，用于禁用 TSR 抗闪烁启发式（UE5.1+） |
| bIsSky | uint8:1 | public | 天空材质标记，Unlit/Opaque 材质可用于天空穹网格 |
| bCastRayTracedShadows | uint8:1 | public | 材质投射光线追踪阴影 |
| bGenerateSphericalParticleNormals | uint8:1 | public | 为使用此材质的粒子生成球形法线 |
| bNormalCurvatureToRoughness | uint8:1 | public | 基于屏幕空间法线变化降低粗糙度 |
| Wireframe | uint8:1 | public | 启用网格线框视图 |
| NumCustomizedUVs | int32 | public | 自定义 UV 输入数量（0-8），未连接的传递顶点 UV |
| ShadingRate | TEnumAsByte\<EMaterialShadingRate\> | public | 可变速率着色率（UE5，平台相关） |
| bAllowVariableRateShading | uint8:1 | public | 允许可变速率着色（UE5） |
| FloatPrecisionMode | TEnumAsByte\<EMaterialFloatPrecisionMode\> | public | 像素着色器浮点精度模式（移动端，UE5，替代 bUseFullPrecision_DEPRECATED） |
| bUseLightmapDirectionality | uint8:1 | public | 使用光照贴图方向性和逐像素法线（移动端） |
| bUseAlphaToCoverage | uint8:1 | public | 遮罩材质使用 Alpha to Coverage（移动端，需 MSAA） |
| StateId | FGuid | public | 唯一标识材质状态，材质表达式等变更时重新生成 |

### 半透明属性字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| TranslucencyPass | TEnumAsByte\<EMaterialTranslucencyPass\> | 半透明渲染 Pass（BeforeDOF/AfterDOF/AfterMotionBlur） |
| TranslucencyLightingMode | TEnumAsByte\<ETranslucencyLightingMode\> | 半透明光照模式 |
| TranslucencyDirectionalLightingIntensity | float | 半透明方向光照强度（增大使法线影响更强） |
| TranslucentShadowDensityScale | float | 半透明阴影密度缩放 |
| TranslucentSelfShadowDensityScale | float | 半透明自阴影密度缩放 |
| TranslucentSelfShadowSecondDensityScale | float | 第二自阴影梯度密度（添加阴影中的趣味着色） |
| TranslucentSelfShadowSecondOpacity | float | 第二自阴影梯度强度 |
| TranslucentBackscatteringExponent | float | 后散射指数（Subsurface 着色模型，方向光体积阴影） |
| TranslucentMultipleScatteringExtinction | FLinearColor | 多次散射消光颜色（体积阴影） |
| TranslucentShadowStartOffset | float | 半透明阴影局部空间偏移（正值远离光源） |
| bScreenSpaceReflections | uint8:1 | 半透明屏幕空间反射 |
| bContactShadows | uint8:1 | 半透明接触阴影 |
| bEnableResponsiveAA | uint8:1 | 响应式抗锯齿（小粒子如火花，仅小移动特征） |
| bDisableDepthTest | uint8:1 | 在不透明像素上方绘制（仅半透明有意义） |
| bWriteOnlyAlpha | uint8:1 | 半透明 Pass 仅写入 Alpha 通道 |
| bEnableMobileSeparateTranslucency | uint8:1 | 移动端独立半透明（不受 Bloom/DOF 影响） |
| bUseTranslucencyVertexFog | uint8:1 | 半透明材质应用雾效（默认 true） |
| bApplyCloudFogging | uint8:1 | 半透明材质接收云雾贡献（需开启 Apply Fogging） |
| bComputeFogPerPixel | uint8:1 | 逐像素计算雾效（修复低曲面细分伪影，开销更高） |
| bOutputTranslucentVelocity | uint8:1 | 半透明材质输出运动矢量并写入速度 Pass 深度缓冲（UE5） |
| bIsTranslucencyVelocityFromDepth | uint8:1 | 仅基于输出深度和相机运动计算速度（UE5） |
| AllowTranslucentCustomDepthWrites | uint8:1 | 允许半透明材质写入自定义深度 |
| bAllowFrontLayerTranslucency | uint8:1 | 允许前层半透明（UE5.1+） |
| bAllowTranslucentLocalLightShadow | uint8:1 | 允许半透明材质接收局部光源阴影 |
| TranslucentLocalLightShadowQuality | float | 半透明局部光源阴影质量（0-1） |
| TranslucentDirectionalLightShadowQuality | float | 半透明方向光阴影质量（0-1） |

### Nanite/Displacement 字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| NaniteOverrideMaterial | FMaterialOverrideNanite | Nanite 渲染替代材质（UE5） |
| bEnableTessellation | uint8:1 | 启用曲面细分（置换贴图的前提条件） |
| bEnableDisplacementFade | uint8:1 | 启用置换淡出（UE5，远处禁用动态置换） |
| DisplacementScaling | FDisplacementScaling | 置换缩放参数（Magnitude 默认 4.0, Center 默认 0.5） |
| DisplacementFadeRange | FDisplacementFadeRange | 置换淡出范围（StartSizePixels 默认 4.0, EndSizePixels 默认 1.0，UE5） |

### 物理材质引用

| 字段名 | 类型 | 用途 |
|--------|------|------|
| PhysMaterial | TObjectPtr\<UPhysicalMaterial\> | 物理材质引用（per D-16，只说明存在） |
| PhysMaterialMask | TObjectPtr\<UPhysicalMaterialMask\> | 物理材质遮罩引用（per D-16，只说明存在） |
| PhysicalMaterialMap | TObjectPtr\<UPhysicalMaterial\>[EPhysicalMaterialMaskColor::MAX] | 物理材质映射数组 |
| RenderTracePhysicalMaterialOutputs | TArray\<TObjectPtr\<UPhysicalMaterial\>\> | 渲染追踪物理材质输出数组 |

### 折射字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| RefractionMethod | TEnumAsByte\<ERefractionMode\> | 折射偏移计算方式 |
| RefractionCoverageMode | TEnumAsByte\<ERefractionCoverageMode\> | 折射是否考虑材质表面覆盖率（仅 Substrate FrontMaterial） |
| RefractionDepthBias | float | 折射深度偏移（防止锐角下近处物体渲染到扭曲表面） |
| PixelDepthOffsetMode | TEnumAsByte\<EPixelDepthOffsetMode\> | 像素深度偏移模式 |

### 后处理材质字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| BlendableLocation | TEnumAsByte\<EBlendableLocation\> | 后处理图中的插入位置 |
| BlendablePriority | int32 | 多个同类型节点的插入顺序和组合优先级 |
| BlendableOutputAlpha | uint8:1 | 后处理材质输出 Alpha |
| bIsBlendable | uint8:1 | 允许混合（后处理专用） |
| UserSceneTexture | FName | 用户生成场景纹理输出（覆盖默认输出） |
| bDisablePreExposureScale | uint8:1 | 禁用后处理材质的预曝光缩放（UE5.1+） |
| bUsedWithNeuralNetworks | uint8:1 | 用于神经网络引擎（UE5.4+，额外推理 Pass） |
| bEnableStencilTest | uint8:1 | 基于自定义深度/模板缓冲的模板测试 |
| StencilCompare | TEnumAsByte\<EMaterialStencilCompare\> | 模板比较函数 |
| StencilRefValue | uint8 | 模板参考值 |

### 移动端/前向渲染字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| bForwardRenderUsePreintegratedGFForSimpleIBL | uint32:1 | 前向渲染使用预积分 GF LUT（多一个采样器） |
| bUseHQForwardReflections | uint8:1 | 前向渲染高质量反射（多个视差校正反射捕获混合） |
| bForwardBlendsSkyLightCubemaps | uint8:1 | 混合天空光立方体贴图 |
| bUsePlanarForwardReflections | uint8:1 | 前向/移动端平面反射（减少一个可用采样器） |

### World Position Offset 字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| MaxWorldPositionOffsetDisplacement | float | WPO 最大位移量（解决剔除和自遮挡问题，0 表示无限制） |
| bAlwaysEvaluateWorldPositionOffset | uint8:1 | 强制始终计算 WPO（忽略图元的禁用设置） |

### Lumen/虚拟纹理字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| bCompatibleWithLumenCardSharing | uint8:1 | 允许不同实例共享 Lumen Cards（UE5，所有组件需设置） |
| bRelaxRuntimeVirtualTextureRestrictions | uint8:1 | 放松运行时虚拟纹理输出限制 |

### Usage 标志

22 个 Usage 标志控制材质可应用于哪些几何类型（对应 EMaterialUsage 枚举，MATUSAGE_MAX = 22）。部分标志的底层类型为 uint32:1（Water/HairStrands/Nanite/VolumetricCloud/StaticMesh/LidarPointCloud/VirtualHeightfieldMesh/HeterogeneousVolumes），其余为 uint8:1。完整列表：

- bUsedWithSkeletalMesh — 骨骼网格
- bUsedWithStaticMesh — 静态网格 (uint32:1)
- bUsedWithNanite — Nanite 几何（UE5, uint32:1）
- bUsedWithParticleSprites — 粒子精灵
- bUsedWithBeamTrails — 光束轨迹
- bUsedWithMeshParticles — 网格粒子
- bUsedWithSplineMeshes — 样条网格
- bUsedWithInstancedStaticMeshes — 实例化静态网格
- bUsedWithGeometryCollections — 几何集合
- bUsedWithWater — 水面 (uint32:1)
- bUsedWithHairStrands — 发丝 (uint32:1)
- bUsedWithVolumetricCloud — 体积云 (uint32:1)
- bUsedWithHeterogeneousVolumes — 异构体积（UE5, uint32:1）
- bUsedWithLidarPointCloud — LiDAR 点云 (uint32:1)
- bUsedWithVirtualHeightfieldMesh — 虚拟高度场网格 (uint32:1)
- bUsedWithVoxels — Nanite 体素（UE5）
- bUsedWithStaticLighting — 静态光照
- bUsedWithMorphTargets — 变形目标
- bUsedWithClothing — 布料
- bUsedWithNiagaraSprites — Niagara 精灵
- bUsedWithNiagaraRibbons — Niagara 带状
- bUsedWithNiagaraMeshParticles — Niagara 网格粒子
- bUsedWithGeometryCache — 几何缓存
- bUsedWithEditorCompositing — 编辑器合成

### 其他字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| MaterialDecalResponse | TEnumAsByte\<EMaterialDecalResponse\> | DBuffer 贴花响应（per D-17，只说明存在） |
| DecalBlendMode | TEnumAsByte\<EDecalBlendMode\> | **已废弃**，使用 TranslucencyPass 替代 |
| DitheredLODTransition | uint8:1 | LOD 抖动过渡（植被系统） |
| DitherOpacityMask | uint8:1 | 抖动不透明度遮罩（结合 Temporal AA 实现有限半透明） |
| bUseEmissiveForDynamicAreaLighting | uint8:1 | 自发光注入光传播体积 |
| bUsedAsSpecialEngineMaterial | uint8:1 | 特殊引擎材质（默认材质/仅光照材质等，编译约 20x 着色器） |
| bSubstrateRoughnessTracking | uint8:1 | Substrate 粗糙度追踪（UE5，禁用后顶层粗糙度不影响底层） |
| bAutomaticallySetUsageInEditor | uint8:1 | 编辑器中自动设置 Usage 标志 |
| bForceCompatibleWithLightFunctionAtlas | uint8:1 | 强制兼容光照函数图集 |
| PreshaderGap | uint16 | 覆盖全局 PreshaderGapInterval（平台特定寄存器溢出 bug 的 workaround） |

WITH_EDITORONLY_DATA 相关字段统一列出（per D-20）。

## 源码引用

- `Runtime/Engine/Public/Materials/Material.h` — UMaterial 类定义（2167 行）
- `Runtime/Engine/Public/Materials/MaterialInterface.h` — UMaterialInterface 基类、EMaterialUsage 枚举
- `Runtime/Engine/Public/Materials/MaterialOverrideNanite.h` — FMaterialOverrideNanite 结构体定义
- `Runtime/Engine/Classes/Engine/EngineTypes.h` — FDisplacementScaling、FDisplacementFadeRange 结构体定义
- `Runtime/Engine/Public/MaterialShared.h` — FMaterialShadingModelField 使用上下文

## 版本差异

| 变更 | 版本 | 说明 |
|------|------|------|
| Substrate 系统 | UE5 | bIsThinSurface、bSubstrateRoughnessTracking 字段 |
| Nanite 系统 | UE5 | NaniteOverrideMaterial、bUsedWithNanite 字段 |
| 置换淡出 | UE5 | DisplacementFadeRange、bEnableDisplacementFade 字段 |
| ShadingModels 字段 | UE4.25+ | 从单值 ShadingModel 变为多着色模型组合 |
| 像素动画标记 | UE5.1+ | bHasPixelAnimation 字段（TSR 抗闪烁优化） |
| 前层半透明 | UE5.1+ | bAllowFrontLayerTranslucency 字段 |
| Lumen 卡片共享 | UE5 | bCompatibleWithLumenCardSharing 字段 |
| 可变速率着色 | UE5 | ShadingRate、bAllowVariableRateShading 字段 |
| 神经网络引擎 | UE5.4+ | bUsedWithNeuralNetworks 字段 |
| 异构体积 Usage | UE5 | bUsedWithHeterogeneousVolumes 标志 |
| 体素 Usage | UE5 | bUsedWithVoxels 标志 |
| 速度缓冲输出 | UE5 | bOutputTranslucentVelocity、bIsTranslucencyVelocityFromDepth 字段 |
| 云雾贡献 | UE5 | bApplyCloudFogging 字段 |
| 移动端精度 | UE5 | FloatPrecisionMode 替代 bUseFullPrecision_DEPRECATED |
| 后处理模板测试 | UE5 | bEnableStencilTest、StencilCompare、StencilRefValue 字段 |
| 后处理 Alpha | UE5 | BlendableOutputAlpha 字段 |
| 预曝光禁用 | UE5.1+ | bDisablePreExposureScale 字段 |
| HLSL 生成器 | UE5.4+ | bEnableNewHLSLGenerator 字段（实验性） |
| HairStrands/Cloud Usage | UE5 | 新增 Usage 标志 |
| 自定义深度写入 | UE5 | AllowTranslucentCustomDepthWrites 字段 |

---
*文档创建: Phase 3 - 材质与纹理资产*
*源码路径: 相对引用 UE Engine 目录*
*最后校验: 基于 UE5.4+ 源码 Material.h (2167 行)*