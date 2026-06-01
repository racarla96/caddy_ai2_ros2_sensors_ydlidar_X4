# caddy_ai2_ros2_sensors_ydlidar_x4

**ROS 2:** Jazzy | **Gazebo:** Harmonic | **Sensor:** YDLidar X4

Driver ROS 2 + fragmento URDF inyectable para Gazebo Harmonic del sensor YDLidar X4. Los parámetros operativos se centralizan en `bringup/config/sensor_params.yaml` y se inyectan en tiempo de launch via Jinja2 en los templates del nodo y del modelo URDF.

---

## Estructura

```
caddy_ai2_ros2_sensors_ydlidar_x4/
├── bringup/
│   ├── config/
│   │   ├── sensor_params.yaml              # Parámetros operativos y de simulación
│   │   └── ydlidar_x4_node_params.yaml.j2  # Template Jinja2 → parámetros del nodo
│   ├── launch/
│   │   ├── general.launch.py               # Launch unificado (sim + real)
│   │   ├── real.launch.py                  # Launch hardware real
│   │   └── ydlidar_x4_description.py       # Helper de integración en robots padre
│   └── rviz/
│       └── ydlidar_x4.rviz
├── code/src/
│   ├── ydlidar_node.cpp                    # Nodo driver
│   └── ydlidar_client.cpp                  # Cliente de prueba
├── description/
│   ├── sensor.urdf.j2                      # Fragmento URDF inyectable (Jinja2)
│   └── ydlidar_x4.dae                      # Malla 3D
├── sdk/                                    # YDLidar SDK (vendored)
└── startup/
    └── initenv.sh                          # Udev rule — crea /dev/ydlidar
```

---

## Instalación del dispositivo

Crear el alias `/dev/ydlidar` (se ejecuta una sola vez):

```bash
cd startup/
sudo chmod +x initenv.sh && sudo sh initenv.sh
```

---

## Build

```bash
colcon build --packages-select caddy_ai2_ros2_sensors_ydlidar_x4
source install/setup.bash
```

---

## Parámetros (`bringup/config/sensor_params.yaml`)

| Parámetro | Valor | Descripción |
|---|---|---|
| `frame_id` | `ydlidar_x4_link` | Frame TF del sensor |
| `port` | `/dev/ydlidar` | Puerto serie (alias udev) |
| `baudrate` | 128000 | bps |
| `frequency` | 7.0 Hz | Frecuencia de escaneo |
| `angle_min/max` | −180° / 180° | Rango angular |
| `range_min/max` | 0.12 / 10.0 m | Rango de distancia |
| `resolution` | 0.5° | Resolución angular |
| `simulation.noise.enabled` | `true` | Activar ruido gaussiano en sim |
| `simulation.noise.stddev` | 0.015 m | Desviación estándar del ruido |

---

## Ejecución

### Hardware real

```bash
ros2 launch caddy_ai2_ros2_sensors_ydlidar_x4 general.launch.py
```

---

## Integración en un robot padre

El paquete expone el helper `ydlidar_x4_description.py` con la función `get_sensor_urdf()` que devuelve el fragmento URDF renderizado para insertar en el URDF del robot.

```python
# En spawn_robot.launch.py del robot padre
from ament_index_python.packages import get_package_share_directory
import sys, os

sensor_share = get_package_share_directory('caddy_ai2_ros2_sensors_ydlidar_x4')
sys.path.insert(0, os.path.join(sensor_share, 'bringup', 'launch'))
from ydlidar_x4_description import get_sensor_urdf

fragment = get_sensor_urdf(
    prefix='',
    namespace='',
    x=0.0, y=0.0, z=0.5,
    roll=0.0, pitch=0.0, yaw=0.0,
    gazebo=True,
)
```

### Dependencia en `package.xml` del robot padre

```xml
<exec_depend>caddy_ai2_ros2_sensors_ydlidar_x4</exec_depend>
```

### Bridge en el robot padre (`gz_msg_bridge.yaml.j2`)

```yaml
- ros_topic_name: "{{ ns_prefix }}ydlidar_x4/scan"
  gz_topic_name:  "{{ ns_prefix }}ydlidar_x4/scan"
  ros_type_name:  "sensor_msgs/msg/LaserScan"
  gz_type_name:   "gz.msgs.LaserScan"
  direction:      "GZ_TO_ROS"
  frame_id:       "{{ prefix }}ydlidar_x4_link"
```

---

## Topic publicado

| Topic | Tipo | frame_id |
|---|---|---|
| `/{namespace}/ydlidar_x4/scan` | `sensor_msgs/msg/LaserScan` | `{prefix}ydlidar_x4_link` |

---

## Dependencias

- **ROS 2:** `rclcpp`, `sensor_msgs`, `robot_state_publisher`
- **Python (launch):** `jinja2`, `pyyaml`
- **Build:** `ament_cmake`
- **SDK:** YDLidar SDK (incluido en `sdk/`)
