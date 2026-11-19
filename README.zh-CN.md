# Attitude Atlas · 无人机姿态坐标系工作台

把整段 PX4 和 ROS 2 姿态记录放进浏览器，找出两边从哪一帧开始不一致，再把那一对消息交给同事复现。

**[打开整段日志对比](https://lazyerzzz.github.io/attitude-atlas/logs.html)** · [核对一对消息](https://lazyerzzz.github.io/attitude-atlas/compare.html) · [单姿态工作台](https://lazyerzzz.github.io/attitude-atlas/) · [English](README.md)

[![合成示例中有一处 90° 的误差和一条未匹配样本](media/recording-check.png)](https://lazyerzzz.github.io/attitude-atlas/logs.html)

## 找到同一架次，再查时钟漂移

如果手上有一个 ROS 2 MCAP 或 SQLite bag 和几个名字相似的 ULog，可用 `python bin/find_flight.py capture.mcap logs/*.ulg` 按两侧唯一出现的相同姿态事件排序。选定日志后，运行 `python bin/pair_clocks.py selected.ulg capture.mcap --events-out events.csv`，可分别查看消息采样、MCAP 发布和接收时间。工具支持包含 PX4 姿态镜像的 MCAP 和标准 CDR 布局的 rosbag2 SQLite 文件。[安装与复算步骤](examples/clock-study/)

两组真机记录中，ROS 消息采样时间相对 PX4 分别多走了 **3.014 ms（77 秒）** 和 **5.497 ms（257 秒）**。较长一组前后四分之一时段的等效速率差从 +13.61 增至 +28.43 ppm。用前段拟合偏移和速率后，后段 P95 采样时间残差仍有 0.956 ms。联调时可以据此检查自己的匹配时间窗。[查看两次实测曲线](https://lazyerzzz.github.io/attitude-atlas/clock-study.html)

### 什么时候需要重新标定

另一团队 HALO 公开的 7 组 ULog / ROS 2 bag 来自 3 架 ModalAI VOXL 2。最长一组的 986 个相同事件跨 49.59 秒，ROS 采样时间相对 PX4 多走 0.730 ms。用 10 秒窗口和 0.25 ms 的 P95 预算，其后三个窗口均在预算内。相同设置在原地效记录的第 100.04 秒和 170.04 秒确认重标定，固定模型与自适应模型在相同后续事件上的 P95 残差分别为 2.154 ms 和 0.299 ms。[交互回放全部九组](https://lazyerzzz.github.io/attitude-atlas/segments.html)

```sh
python bin/pair_clocks.py flight.ulg capture.db3 --segment-budget-ms 0.25 --window-s 10
```

报告会列出何时能确认切换、旧模型与候选模型各自的残差，以及可复用的纳秒级标定参数。另 6 组 HALO 记录的匹配跨度只有 7.15–19.35 秒，默认窗口下均返回证据不足。两批数据的时间桥接路径与记录时长不同，测得的 ppm 仅描述对应记录中的等效速率差。

**提前重标定的效果取决于记录。** 可选的 `headroom` 策略把地效记录同一批 2,795 个后续事件的 P95 从 0.299 降到 0.185 ms，预算仍为 0.25 ms。对两条 VOXL 2 长同步交换序列，约 603 秒的一条改善，约 328 秒的一条退步。两条序列分别有 79.05 秒和 98.40 秒可由独立 ULog 的相同姿态事件核对。使用 `--segment-budget-ms 0.25 --segment-policy both` 可以在自己的配对日志上比较两种规则。[查看留出测试和误报、漏报](https://lazyerzzz.github.io/attitude-atlas/transfer.html) · [复算步骤](examples/clock-study/TRANSFER.md)

## 从一段日志定位到一帧

内置合成示例有 22 条 ROS 样本。在 5 ms 时间窗内有 21 条匹配，最后一条超出时间窗。第 95 百分位显示为 0.00°，第 13 条却出现了 90° 滚转误差。点击最高点即可检查两架飞机的姿态，也可以复制带复现链接的 Markdown 报告。

1. 用 `ulog2csv -m vehicle_attitude flight.ulg` 导出 PX4 CSV。录制或回放 ROS bag 时，运行 `ros2 topic echo /odom --full-length > ros.yaml` 保存一个带时间戳的话题，按 Ctrl+C 结束。
2. 两份数据须分别符合 FRD → NED 和 FLU → 地理 ENU 的约定。确认使用同一时钟和时间原点，或输入同一物理时刻的两个已知读数（PX4 微秒、ROS 纳秒）。单个同步点校正常量偏移，补充第二个同步点后可在两点之间校正速率差。时钟重启需分段处理。
3. 选择允许的最大配对时间差。页面为每条 ROS 消息寻找最近的 PX4 样本，等距时取较早样本。可检查覆盖率、复用的样本与误差峰值。导出 CSV 保留未匹配行、两侧原始时间戳以及对齐后的时间差。

浏览器在本地处理文件，每个文件上限 16 MiB。命令行支持 CSV，安装 pyulog 且 `ulog2csv` 在 PATH 中时也可以直接读取 `.ulg`。下面的命令运行内置样例：

```sh
node bin/check-recording.mjs site/samples/roll-spike.csv site/samples/roll-spike.yaml \
  --shared-clock --max-skew-ms 5 --rows-out rows.csv --case-out worst.json
```

可以用 `--max-error-deg 2 --min-coverage-pct 95` 设置回归条件。通过返回 0，超限或零匹配返回 1，输入或读写错误返回 2。不同时间原点可用 `--px4-anchor-us US --ros-anchor-ns NS` 替代 `--shared-clock`。第二个同步点使用 `--px4-end-us US --ros-end-ns NS`。两点模式会将标定区间外的样本计为未匹配。输出文件使用新路径。

## 核对自己的两条消息

1. 在 Bridge check 的左右输入框分别粘贴 PX4 和 ROS 消息，点击 Compare attitudes。支持四个数值、JSON，以及单条 `ros2 topic echo --once` 的 YAML 输出。
2. 页面按 PX4 的 FRD → NED 和 ROS 的 FLU → 地理 ENU 进行转换。使用自定义 map、odom 或传感器安装坐标系时，先对齐参考系。输入原始模长和 ROS 帧名可在结果下方核对。
3. 只有确认两条消息共用时钟和时间原点时，才勾选时间复选框。偏移为 ROS 时间减 PX4 时间，单位毫秒。更换任一消息后需要重新确认。
4. 复制对比链接可以让同事复现同一对姿态。导出的 JSON 可重新打开，也可用于自动回归测试。分享内容包含提取的姿态、时间戳、帧名和时钟选择。

仓库附有一个可直接运行的回归案例：

```sh
node bin/check-case.mjs examples/north-roll.json --max-error-deg 1
```

本例中两架飞机机头朝向相同，滚转相差 90°，会超过 1° 容差并返回退出码 1。要检查新版本节点的输出，可追加 `--ros observed.yaml`。通过检查返回 0，数据或参数无效返回 2。

## 先试一个容易判断的姿态

打开 [水平朝北的示例](https://lazyerzzz.github.io/attitude-atlas/#q=1,0,0,0)。PX4 显示的四元数是 `[1, 0, 0, 0]`，ROS 2 显示 `[0, 0, 0.707107, 0.707107]`。在地理 ENU 坐标系里，零偏航指向东，朝北对应 +90°。再从 Example pose 里选 **Level, facing east**，这次 ROS 一侧会显示单位四元数。拖动视图可以换观察角度，右侧三个滑块可以改变飞机姿态。

| 数据来源 | 机体坐标系 | 世界坐标系 | 四元数顺序 |
|---|---|---|---|
| PX4 vehicle_attitude | 前、右、下 | 北、东、下 | w, x, y, z |
| ROS 2 地理局部坐标系 | 前、左、上 | 东、北、上 | x, y, z, w |

两行都表示从机体系到世界系的旋转。如果 ROS 的 map 或 odom 有自定义朝向，还需要使用实际的世界系对齐关系。

## 用自己的数据

- **Quaternion** 支持粘贴消息原文，或逗号和空格分隔的四个分量，先选输入约定，再点 Apply quaternion。
- **Replay** 可以播放内置的约八秒 PX4 姿态记录，也可以打开自己的 CSV。安装 pyulog 后，用 `ulog2csv -m vehicle_attitude flight.ulg` 导出，再打开生成的 `*_vehicle_attitude_0.csv`。需要微秒时间戳 `timestamp` 和 `q[0]` 至 `q[3]`，文件上限为 16 MiB。如果存在 pose_frame 列，每行均须明确为 NED（1）。可逐样本前后步进，并查看当前姿态已保持的时间。
- **Copy pose link** 生成可贴进 GitHub issue 的链接，包含当前姿态的四个分量。CSV 在本地浏览器处理。
- **Export test case** 下载 JSON，包含两套四元数、轴约定、分量顺序，以及机头单位向量在两个世界系里的期望值。

## 本地运行

仓库根目录运行 `python3 -m http.server 8000 --directory site`，然后访问 <http://localhost:8000>。使用 Node.js 18 或更高版本运行 `node --test tests/*.test.mjs` 即可验证转换。

[示例数据来源和授权](README.md#sample-data) · [PX4 坐标转换实现](https://github.com/PX4/px4_ros_com/blob/main/include/px4_ros_com/frame_transforms.h) · [ROS REP 103](https://www.ros.org/reps/rep-0103.html)
