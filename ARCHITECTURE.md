# Arquitectura estándar de paquete sensor ROS 2 + Gazebo Harmonic

Documento de referencia para replicar esta metodología en otros sensores.
Generado a partir del paquete `caddy_ai2_ros2_sensors_sick_lms_291`.

---

## Estructura de ficheros

```
caddy_ai2_ros2_sensors_<tipo>_<modelo>/
├── CMakeLists.txt
├── package.xml
├── README.md
├── ARCHITECTURE.md
├── code/src/
│   └── <sensor>_node.cpp          # Driver ROS 2 (hardware real)
├── bringup/
│   ├── config/
│   │   ├── sensor_params.yaml          # Parámetros operativos (claves planas)
│   │   └── <sensor>_node_params.yaml.j2 # Template → parámetros del nodo ROS 2
│   ├── launch/
│   │   ├── general.launch.py           # Launch unificado sim + real
│   │   └── <sensor>_description.py     # Helper: get_sensor_sdf()
│   └── rviz/
│       └── <sensor>.rviz
├── description/
│   ├── sensor.sdf.j2                  # Fragmento inyectable
│   └── world.sdf.j2                   # Mundo Gazebo o modelo standalone
└── meshes/
    └── <sensor>.dae
```

---

## Principios de diseño

### 1. Separación entre parámetros operativos y constantes físicas

- **`sensor_params.yaml`** — solo parámetros que cambian en runtime o por configuración:
  puerto serie, baudrate, resolución angular, frecuencia, ángulos, rangos.
- **Constantes físicas** (masa, inercia, noise model, frame offset) — hardcodeadas
  directamente en `sensor.sdf.j2`. No van en el YAML.

### 2. Dos plantillas SDF, un pipeline Jinja2

Solo existen dos templates SDF:

| Fichero | Rol |
|---------|-----|
| `sensor.sdf.j2` | Fragmento inyectable dentro de cualquier `<model>` |
| `world.sdf.j2` | Orquesta el mundo Gazebo o el modelo standalone para RSP |

`world.sdf.j2` hace `{% include 'sensor.sdf.j2' %}` — toda la lógica del sensor
está en un único sitio.

### 3. Un solo launch

`general.launch.py` cubre todos los casos mediante argumentos:

| Argumento | Efecto |
|-----------|--------|
| `sim:=true` | Gazebo + bridge + RSP |
| `sim:=false` | driver hardware + RSP |
| `rsp:=false` | desactiva RSP (el sistema padre lo lanza) |
| `rviz:=false` | desactiva RViz2 |

---

## Diseño de sensor.sdf.j2

### Origen del link = apertura física del sensor

El origen del link principal (`<sensor>_link`) se coloca en el punto donde el
sensor emite/recibe físicamente (apertura óptica, cabeza de escáner, etc.).
Visual, colisión e inercia llevan un offset negativo en Z para alinearse con
el cuerpo físico.

```
Z=0     → origen del link = apertura óptica (frame_id del scan)
Z=-0.025 → mesh visual (cuerpo del sensor)
```

Esto elimina la necesidad de un link secundario solo para el frame del scan.

### Flag `include_parent_joint`

Controla si el fragmento crea su propia estructura de anclaje:

```
include_parent_joint=true  (defecto)
  → añade <link name="{{ parent_link }}"/> si parent_link == "map"
  → añade <joint parent_link → sensor_link>
  → uso: standalone (RSP) o inyección directa en modelo padre

include_parent_joint=false
  → solo el link del sensor con <pose>0 0 0 0 0 0</pose>
  → uso: world.sdf.j2 modo world (la pose la da <model><pose>)
```

### Flag `with_sensor`

```
with_sensor=true  (defecto en sensor.sdf.j2)
  → incluye bloque <sensor> de Gazebo

with_sensor=false
  → solo links y joints → seguro para sdformat_urdf / robot_state_publisher
```

### Anchor link para sdformat_urdf

`sdformat_urdf` tiene la restricción: **el link canónico del modelo no puede
ser hijo de un joint**. Para modelos standalone (RSP), se añade un link vacío
con el nombre del frame padre antes del link del sensor:

```xml
<!-- solo cuando parent_link == "map" -->
<link name="map"/>

<link name="lidar_sick_lms_291_link">
  <pose>x y z r p y</pose>
  ...
</link>

<joint name="lidar_joint" type="fixed">
  <parent>map</parent>
  <child>lidar_sick_lms_291_link</child>
</joint>
```

`map` es el link canónico (root). `lidar_sick_lms_291_link` es child → sin error.
RSP publica el TF `map → lidar_sick_lms_291_link`.

> **Nota**: El anchor solo se crea cuando `parent_link == "map"` porque `world`
> está reservado en ROS 2 / sdformat_urdf. Para otros frames globales que se
> usen en otros proyectos, ampliar la condición:
> `{% if parent_link in ["map", "odom"] %}`

### Pose del link según contexto

```jinja2
{% if include_parent_joint | default(true) %}
    <pose>{{ x }} {{ y }} {{ z }} {{ roll }} {{ pitch }} {{ yaw }}</pose>
{% else %}
    <pose>0 0 0 0 0 0</pose>
{% endif %}
```

- `include_parent_joint=true` → la pose del link posiciona el sensor en el modelo
- `include_parent_joint=false` → la pose es 0 porque `<model><pose>` lo maneja Gazebo

**IMPORTANTE**: No usar `<pose relative_to="{{ parent_link }}">` dentro de un
`<model>`. sdformat_urdf no puede resolver frames externos al scope del modelo
y lanza error `relative_to name[X] does not exist`.

---

## Diseño de world.sdf.j2

```
model_only=false  (defecto)
  → <sdf><world> completo
  → sensor horneado directamente en el mundo (include_parent_joint=false,
    la pose va en <model><pose>)
  → gui con todos los plugins Gazebo Harmonic

model_only=true
  → <sdf><model> para robot_state_publisher
  → include_parent_joint=true (defecto) → anchor link + joint → TF correcto
  → with_sensor controla si lleva el bloque <sensor>
```

### No usar spawn separado

El sensor va horneado en el mundo SDF con `with_sensor=True`:

```python
world_str = env.get_template('world.sdf.j2').render(**sensor, gui=True, with_sensor=True)
```

Esto elimina la necesidad de `caddy_ai2_ros2_robot_description_publisher`
o cualquier mecanismo de spawn vía topic.

---

## Plugins GUI Gazebo Harmonic (gz-sim8)

Lista completa de plugins necesarios para GUI funcional. El orden importa.

```xml
MinimalScene            <!-- escena 3D, SIEMPRE primero -->
EntityContextMenuPlugin <!-- menú contextual, necesario para Shapes/TransformControl -->
GzSceneManager          <!-- gestión de escena -->
InteractiveViewControl  <!-- navegación con ratón -->
CameraTracking
MarkerManager           <!-- necesario para feedback visual al colocar objetos -->
SelectEntities          <!-- selección de entidades -->
Spawn                   <!-- spawn desde SDF/Fuel -->
VisualizationCapabilities
WorldControl            <!-- play/pause/step -->
WorldStats              <!-- sim time, real time -->
Shapes                  <!-- barra insertar primitivas -->
Lights                  <!-- barra insertar luces -->
TransformControl        <!-- mover/rotar/escalar entidades -->
VisualizeLidar          <!-- visualización scan lidar -->
ComponentInspector      <!-- inspector de componentes (docked) -->
EntityTree              <!-- árbol de entidades (docked) -->
```

**Pitfall crítico**: Los anchors de posición en `WorldControl` y `WorldStats`
usan el atributo `target`, NO `with`:
```xml
<!-- CORRECTO -->
<line own="left" target="left"/>
<!-- INCORRECTO — causa crash basic_string: construction from null -->
<line own="left" with="left"/>
```

---

## Pipeline de renderizado en general.launch.py

```python
# 1. Cargar parámetros operativos
with open('.../sensor_params.yaml') as f:
    params = yaml.safe_load(f)

# 2. Diccionarios de variables
base   = {prefix, parent_link, x, y, z, roll, pitch, yaw, mesh_uri}
sensor = {**base, namespace, angle_min, angle_max, range_min, range_max,
          resolution, frequency, use_gpu, noise_enabled}

# 3. Modelo para RSP (siempre, sim y real)
rsp_sdf = world.sdf.j2(**base, model_only=True, with_sensor=False)

# 4a. Simulación → mundo completo con sensor horneado
world_str = world.sdf.j2(**sensor, gui=True, with_sensor=True)

# 4b. Hardware real → parámetros del nodo driver
node_params = <sensor>_node_params.yaml.j2(**params)
```

---

## Nodo helper get_sensor_sdf()

Fichero: `bringup/launch/<sensor>_description.py`

Expone `get_sensor_sdf()` para que otros paquetes puedan obtener el fragmento
SDF del sensor sin copiar el código de renderizado Jinja2.

### Uso desde otro launch

```python
# 1. package.xml del robot padre:
#    <exec_depend>caddy_ai2_ros2_sensors_<tipo>_<modelo></exec_depend>

# 2. En _launch() / OpaqueFunction del robot padre:
import sys, os
from ament_index_python.packages import get_package_share_directory

pkg = get_package_share_directory('caddy_ai2_ros2_sensors_<tipo>_<modelo>')
sys.path.insert(0, os.path.join(pkg, 'bringup', 'launch'))
from <sensor>_description import get_sensor_sdf

fragment = get_sensor_sdf(
    prefix='front_',
    parent_link='base_link',  # link real del robot (ya existe en el modelo)
    x=0.30, z=0.50,
    with_sensor=True,
    namespace='robot1',
    use_gpu=True,
)

# 3. En robot.sdf.j2 del robot padre:
# {{ sick_sensor }}  ← dentro del bloque <model>
```

**Regla**: `sys.path.insert` SIEMPRE dentro de `_launch()`, nunca a nivel de módulo.

### Arrancar solo el driver (hardware real, RSP externo)

```python
IncludeLaunchDescription(
    PythonLaunchDescriptionSource('.../general.launch.py'),
    launch_arguments={
        'sim':  'false',
        'rviz': 'false',
        'rsp':  'false',   # RSP lo lanza el sistema padre
    }.items(),
)
```

---

## Pitfalls conocidos y soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| `basic_string: construction from null` en Gazebo GUI | Atributo `with` en lugar de `target` en anchors de WorldControl/WorldStats | Cambiar `<line own="X" with="Y"/>` → `<line own="X" target="Y"/>` |
| `relative_to name[world] does not exist` en sdformat_urdf | `<pose relative_to="world">` dentro de `<model>` — el scope de modelo no ve frames externos | Usar `<pose>x y z r p y</pose>` sin `relative_to` |
| `Canonical link must not be a child of a joint` | El único link del modelo tiene un joint encima | Añadir `<link name="{{ parent_link }}"/>` ANTES del link principal |
| `<model> tags with <pose> are not currently supported` | `<model><pose>` en bloque `model_only` pasado a sdformat_urdf | Eliminar `<pose>` del bloque `model_only`; la pose la gestiona el launch |
| Gazebo crash `GzScene3D` | Plugin eliminado desde Gazebo Garden | Reemplazar por `MinimalScene` + `GzSceneManager` + `InteractiveViewControl` + `CameraTracking` |
| No se pueden añadir objetos con Shapes | Falta `EntityContextMenuPlugin` o `MarkerManager` | Añadir ambos antes de `SelectEntities` en el bloque GUI |
| `package://` URI no resuelto en Gazebo | Gazebo solo resuelve `package://` vía topic `/robot_description` | Usar siempre `file://` con ruta absoluta construida en Python |
| Scan points no visibles en RViz | `frame_id` del scan no existe en TF | Verificar que RSP recibe el modelo con el link anchor correcto |

---

## Checklist para un nuevo sensor

- [ ] Crear estructura de directorios según plantilla
- [ ] `sensor_params.yaml` — solo parámetros operativos (sin constantes físicas)
- [ ] `sensor.sdf.j2` — origen del link en la apertura física; offsets en visual/collision/inertial
- [ ] `sensor.sdf.j2` — anchor link `{% if parent_link == "map" %}` antes del link principal
- [ ] `sensor.sdf.j2` — pose sin `relative_to`; condicional según `include_parent_joint`
- [ ] `world.sdf.j2` — bloque world con `{% set include_parent_joint = false %}`
- [ ] `world.sdf.j2` — plugins GUI en orden correcto con atributo `target` (no `with`)
- [ ] `general.launch.py` — argumentos: `sim`, `rviz`, `rsp`, `use_noise`, `use_gpu`, `prefix`, `namespace`, `parent_link`, `x`, `y`, `z`, `roll`, `pitch`, `yaw`
- [ ] `general.launch.py` — mundo horneado con sensor (`with_sensor=True`), sin spawn separado
- [ ] `<sensor>_description.py` — helper `get_sensor_sdf()` con todos los parámetros
- [ ] `<sensor>_node_params.yaml.j2` — `frame_id` apunta al link principal (no a un frame separado)
- [ ] `README.md` — documentar inyección, Opción A (launch) y Opción B (fragmento SDF)
