# coordination_oru
This package provides an online coordination method for multiple robots. It is based on the Meta-CSP Framework library available at <a href="http://metacsp.org">metacsp.org</a>. This package includes a basic 2D robot simulation, and does not require ROS or ROSJava. A plugin that enables the use of this package with the <a href="https://github.com/OrebroUniversity/navigation_oru-release">navigation_oru</a> package will be provided in the near future.

## Overview
The coordination method is based on the trajectory envelope representation provided by the Meta-CSP framework. A _trajecotry envelope_ is a set of spatio-temporal constraints on a robot's trajectory. A trajecotry envelope spans over a _path_, which is a sequence of _poses_ ```<p1, ... pn>```. In the current implementation, the spatial constraints defining a trajectory enevlope are computed as the sweep of the robot's footprint over the path. For more details on trajectory envelopes, please see

* Federico Pecora, Marcelo Cirillo, Dimitar Dimitrov, <a href="http://ieeexplore.ieee.org/abstract/document/6385862/">On Mission-Dependent Coordination of Multiple Vehicles under Spatial and Temporal Constraints</a>, IEEE/RSJ International Conference on Intelligent Robots and Systems (2012), pp. 5262-5269.

The coordination algorithm provided in this implementation works as follows:

* For each pair of trajecotry envelopes (```te1```, ```te2```) of two distinct robots, compute the areas of spatial intersection of the trajectory envelopes. Each such contiguous area is a _critical section_, defined as a tuple (```te1```, ```te2```, [```start1```, ```end1```], [```start2```, ```end2```]), where
  * ```te1``` and ```te2``` are trajectory envelopes that intesect in the critical section
  * ```start1``` (```start2```) is the pose along the path navigated by the robot occupying ```te1``` (```te2```) from which this robot's footprint intersects ```te2``` (```te1```)
  * ```end1``` (```end2```) is the pose along the path navigated by the robot occupying ```te1``` (```te2```) from which this robot's footprint ceases to intersect ```te2``` (```te1```)
* For each robot, select the critical section (```te1```, ```te2```, [```start1```, ```start2```], [```end1```, ```end2```]) such that
  * the index of ```start2``` is minimum
  * the current pose of the robot navigating ```te1``` has not reached ```end1```
* For each critical section (```te1```, ```te2```, [```start1```, ```start2```], [```end1```, ```end2```]) selected at the previous step, instruct the robot navigating ```te2``` that it cannot proceed beyond a _critical point_ ```p``` defined as max(```start2```, ```start2``` + (```cp1``` - ```start1```) - ```s```, where
  * ```cp1``` is the index of the current pose of the robot navigating ```te1``` along the path to ```te1```
  * ```s``` is a safety distance

Critical sections are updated whenever a new mission is added, and critical points for each robot are updated at a specified control period (by default, 1000 msec).

## Installation
To install, clone this repository and compile the source code with gradle (redistributable included):

```
$ git clone https://github.com/FedericoPecora/coordination_oru.git
$ cd coordination_oru
$ ./gradlew install
```

## Running an example
To run an example, issue the following command from the source code root directory:
```
$ ./gradlew run
```
The example continuously posts missions for three robots to reach locations along intersecting paths. The paths are stored in files provided in the ```paths``` directory. The poses of locations and pointers to relevant path files between locations are stored in the self-explanatory ```paths/test_poses_and_path_data.txt``` file.

Running the above example opens a GUI showing the current state of the three robots.

![alt text](images/coord.png "Coordination GUI")

A gray arrow between two robots indicates that the source robot will yield to the target robot. Priorities are computed every time a new mission is added. If multiple missions are added in batch, yielding behavior follows a fixed priority which can be specified programmatically. Driving robots always have priority over robots whose missions have been newly computed. The specific poses at which robots yield are computed on the fly based on the current positions of robots and the intersecting areas of their trajectory envelopes (critical sections). This makes it possible to achieve "following" behavior, that is, the yielding pose of a robot is updated online while the "leading" robot drives.

More detailed information is posted in the terminal. It can be inspected offline by running class ```coordination_oru.util.BrowseLogs```, which opens a log browsing GUI. The GUI shows a panel with the output of each thread that ran in the previous execution of the test program. Messages produced concurrently with the one at the current caret position are highlighted.

![alt text](images/logs.png "LogBrowser GUI")
