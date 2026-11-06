# vcos_components_runtime代码仓库说明

## 1. 代码仓库简介

vcos_components_runtime为VCOS提供的应用运行时环境，包含应用间及应用和系统功能组件、OS间的通信接口、应用软件调度管理
主要提供以下功能：

- 通信栈PDU及多核部署配置支持
- 分区和Core信息配置
- 应用软件间的SR、CS、mode switch同核和跨核通信接口
- 应用软件和系统功能组件、OS间的通信接口
- 应用软件间的internal、external trigger接口
- 应用软件的调度管理，支持调度表和基于alarm的调度

## 2. 代码目录

vcos_components_runtime源代码在haloosspace/vcos/components/runtime目录下，目录结构如下图所示：

```text
runtime                 # VCOS为应用软件提供的运行时环境
├── EcuC                # EcuC模块实现，只包含配置项、校验规则，无动态代码
│   └── config_plug_in  # EcuC模块的configurator工具配置插件，支持UI配置和校验
├── README.md           # vcos_components_runtime的说明文档，主要讲解vcos_components_runtime包含的功能特性及目录结构说明（即本文）
└── Rte                 # Rte模块实现，为应用软件提供运行时环境
    └── config_plug_in  # Rte模块的configurator工具配置插件，支持UI配置和校验规则，推理和动态代码生成在configurator中实现
```

## 3. 仓库使用入门

该仓库中包含的Rte模块和EcuC模块支持在configurator工具中配置，需要在configurator工具添加该模块并进行配置、校验通过并生成动态代码后，才会在生成动态代码的CMakeLists.txt中打开该模块的编译开关 configurator工具的使用请参考[配置工具开发者手册](https://gitee.com/haloos/vcos/blob/master/user_manual/studio/configurator_tool_user_manual.md)

EcuC模块主要功能包含：

- 支持Os模块的核和分区相关信息配置
- 支持通信栈各模块间PDU的映射关系配置，并为通信栈的多核部署提供相应的配置参数

EcuC模块详细的配置参数说明参考[EcuC模块配置项说明](https://gitee.com/haloos/vcos/blob/master/configuration_reference/ecuc_cfg.md)。EcuC仅为通信栈和Os提供辅助配置信息，不包含静态或动态源代码，因此本模块不需参与编译

Rte模块根据ASW runnable和BSW schedule entity的task mapping信息，以及port连接信息进行推理，生成实时运行环境。因此，Rte模块没有静态代码，只在configurator工具中推理和生成动态代码。Rte模块的使用参考[配置工具开发者手册](https://gitee.com/haloos/vcos/blob/master/user_manual/studio/configurator_tool_user_manual.md) 4.2.4节内容。Rte模块详细的配置参数说明参考[Rte模块配置项说明](https://gitee.com/haloos/vcos/blob/master/configuration_reference/rte_cfg.md)
