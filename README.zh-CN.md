# Attitude Atlas · 无人机姿态坐标系工作台

把飞控发出的 PX4 姿态和 ROS 节点收到的姿态并排放进浏览器，可以看到两个机体朝向、完整旋转误差，以及前、左、上三个机体轴各自偏了多少度。

**[试试 90° 滚转案例](https://lazyerzzz.github.io/attitude-atlas/compare.html#example=roll)** · [单姿态工作台](https://lazyerzzz.github.io/attitude-atlas/) · [English](README.md)

[![两个机头都朝北，右翼滚转了 90°](media/bridge-check.png)](https://lazyerzzz.github.io/attitude-atlas/compare.html#example=roll)

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
