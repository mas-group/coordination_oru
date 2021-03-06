#!/usr/bin/env python
# coding: utf-8

import numpy as np
import os
import errno
import sys
import argparse
import pandas as pd
import re
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
from ctypes import *
from Utils import *

class DataLoader:
    def __init__(self):
        self.fleet_missions = None

    def get_log_files(self, map_name, planner, nRobots, holonomic, use_hotspots, nExperiences):
        sampling_name = "UsingHotspots" if use_hotspots else "Uniform"
        kinematics = "Holonomic" if holonomic else "ReedsSheep"
        planner_names = ["SIMPLE(RRT-Connect)", "Lightning", "Thunder", "EGraphs", "SIMPLE(RRT-Star)"]
        common_directory = os.path.abspath(os.path.split(os.path.abspath(sys.argv[0]))[0]  + "/../../generated/executionData/")
        directory = os.path.join(common_directory, map_name)
        directory = os.path.join(directory, planner_names[planner])
        directory = os.path.join(directory, str(nRobots)+"_Robots")
        directory = os.path.join(directory, kinematics)
        directory = os.path.join(directory, sampling_name)
        directory = os.path.join(directory, str(nExperiences)+"_TrainingExperiences/Logs")

        planning_csv_filename = "Planning.csv"
        execution_csv_filename = "Execution.csv"
        planning_csv_filename = os.path.abspath(os.path.join(directory, planning_csv_filename))
        execution_csv_filename = os.path.abspath(os.path.join(directory, execution_csv_filename))

        assert os.path.isfile(planning_csv_filename), "Planning CSV log file does not exist! \nPath specified was:\n{}".format(planning_csv_filename)
        assert os.path.isfile(execution_csv_filename), "Execution CSV log file does not exist! \nPath specified was:\n{}".format(execution_csv_filename)
        
        relative_dir = os.path.relpath(directory, common_directory)

        return planning_csv_filename, execution_csv_filename, relative_dir

    def load_data(self, map_name="BRSU_Floor0", planner=1, nRobots=5, holonomic=True, use_hotspots=True, nExperiences=100):
        planning_data_file, execution_data_file, rel_dir = self.get_log_files(map_name, planner, nRobots, holonomic, use_hotspots, nExperiences)
        planning_df = pd.read_csv(planning_data_file, index_col=None)
        execution_df = pd.read_csv(execution_data_file, index_col=None)

        fleet_data = self.load_fleet_missions(planning_df, execution_df, nExperiences)
        print("\tLoaded", len(fleet_data), "fleet missions from", rel_dir)
        self.add_loaded_data_to_dict(map_name, planner, nRobots, holonomic, use_hotspots, nExperiences, fleet_data)

    def load_fleet_missions(self, planning_df, execution_df, nExperiences):
        col = "Test Start Time"
        test_start_times = planning_df[col].values.tolist()
        test_start_times = sorted(set(test_start_times))

        fleet_missions = []
        for fleet_id, start_time in enumerate(test_start_times):
            fleet_planning_df = planning_df.loc[planning_df[col] == start_time]
            fleet_execution_df = execution_df.loc[execution_df[col] == start_time]
            fleet_missions.append(FleetMissionData(fleet_planning_df, fleet_execution_df, nExperiences))
        return fleet_missions

    def add_loaded_data_to_dict(self, map_name, planner, nRobots, 
                                holonomic, use_hotspots, nExperiences, fleet_data):
        if self.fleet_missions is None:
            self.fleet_missions = {map_name:{planner:{nRobots:{holonomic:{use_hotspots:{nExperiences:fleet_data}}}}}}
            return
        
        if map_name not in self.fleet_missions.keys():
            self.fleet_missions[map_name] = {planner:{nRobots:{holonomic:{use_hotspots:{nExperiences:fleet_data}}}}}
            return

        if planner not in self.fleet_missions[map_name].keys():
            self.fleet_missions[map_name][planner] = {nRobots:{holonomic:{use_hotspots:{nExperiences:fleet_data}}}}
            return

        if nRobots not in self.fleet_missions[map_name][planner].keys():
            self.fleet_missions[map_name][planner][nRobots] = {holonomic:{use_hotspots:{nExperiences:fleet_data}}}
            return

        if holonomic not in self.fleet_missions[map_name][planner][nRobots].keys():
            self.fleet_missions[map_name][planner][nRobots][holonomic] = {use_hotspots:{nExperiences:fleet_data}}
            return

        if use_hotspots not in self.fleet_missions[map_name][planner][nRobots][holonomic].keys():
            self.fleet_missions[map_name][planner][nRobots][holonomic][use_hotspots] = {nExperiences:fleet_data}
            return

        self.fleet_missions[map_name][planner][nRobots][holonomic][use_hotspots][nExperiences] = fleet_data

    def get_fleet_data(self, map_name="BRSU_Floor0", planner=1, nRobots=5,
                       holonomic=True, use_hotspots=True, nExperiences=100):
        data = self.fleet_missions[map_name][planner][nRobots][holonomic][use_hotspots][nExperiences]

        assert data is not None, "Could not retreive fleet data. Possibly data was not loaded!"

        return data


class MultiLogAnalyzer:
    def __init__(self):
        self.data_loader = DataLoader()
        self.dwt = DWT()
        self.plot_utils = PlotUtils()

        self.dataframe_columns = ["Map", "Planner", "NumRobots", "Kinematics", "SamplingStrategy", "NumExperience", "TotalPlanningTime",
                                  "NumPlansFromRecall", "NumPlansFromScratch", "MaxExecutionTime"]

    def load_all_fleets(self, maps, planners, nRobots, holonomic, use_hotspots, nExperiences):
        print("Loading all fleets...")
        for m in maps:
            for p in planners:
                for r in nRobots:
                    for h in holonomic:
                        for hp in use_hotspots:
                            for e in nExperiences:
                                self.data_loader.load_data(m, p, r, h, hp, e)
        print("All fleets successfully loaded.")

    def get_variables(self, maps, planners, nRobots, holonomic, use_hotspots, nExperiences):
        # Detect variables
        is_param_variable = []
        is_param_variable.append(len(maps) > 1)
        is_param_variable.append(len(planners) > 1)
        is_param_variable.append(len(nRobots) > 1)
        is_param_variable.append(len(holonomic) > 1)
        is_param_variable.append(len(use_hotspots) > 1)
        is_param_variable.append(len(nExperiences) > 1)

        return is_param_variable

    def clean_planner_name(self, planner_name):
        if "SIMPLE" in planner_name:
            planner_name = planner_name.split("(")[1]
            planner_name = planner_name.split(")")[0]
        return planner_name

    def get_figure_title(self, prefix, maps, planners, nRobots, holonomic, use_hotspots, nExperiences, is_param_variable):
        title = prefix + "\n"
        if not is_param_variable[0]:
            title += "Map:{}, ".format(maps[0])
        if not is_param_variable[1]:
            title += "Planner:{}, ".format(self.clean_planner_name(planners[0]))
        if not is_param_variable[2]:
            title += "Num of robots:{}, ".format(nRobots[0])
        if not is_param_variable[3]:
            kinematics = "Holonomic" 
            if not holonomic[0]:
                kinematics = "ReedsSheep"
            title += "Kinematics:{}, ".format(kinematics)
        if not is_param_variable[4]:
            sampling_name = "UsingHotspots"
            if not use_hotspots[0]:
                sampling_name = "Uniform"
            title += "Sampling:{}, ".format(sampling_name)
        if not is_param_variable[5]:
            title += "Experience Count:{}, ".format(nExperiences[0])
        return title

    def get_variable_name(self, prefix, params, is_param_variable):
        planner_names = ["SIMPLE(RRT-Connect)", "Lightning", "Thunder", "EGraphs", "SIMPLE(RRT-Star)"]
        variable_name = prefix
        if is_param_variable[0]:
            if len(variable_name) > 0:
                variable_name += "-\n"
            variable_name += params[0]
        if is_param_variable[1]:
            if len(variable_name) > 0:
                variable_name += "-\n"
            variable_name += self.clean_planner_name(planner_names[params[1]])
        if is_param_variable[2]:
            if len(variable_name) > 0:
                variable_name += "-\n"
            variable_name += str(params[2]) + "Robots"
        if is_param_variable[3]:
            kinematics = "Holonomic" 
            if not params[3]:
                kinematics = "ReedsSheep"
            if len(variable_name) > 0:
                variable_name += "-\n"
            variable_name += kinematics
        if is_param_variable[4]:
            sampling_name = "UsingHotspots"
            if not params[4]:
                sampling_name = "Uniform"
            if len(variable_name) > 0:
                variable_name += "-\n"
            variable_name += sampling_name
        if is_param_variable[5]:
            if len(variable_name) > 0:
                variable_name += "-\n"
            variable_name += str(params[5]) + "Exp"
        return variable_name

    def get_unique_params(self, params):
        params = np.array(params)
        return list(set(params[:, 0])), list(set(params[:, 1])), list(set(params[:, 2])),\
               list(set(params[:, 3])), list(set(params[:, 4])), list(set(params[:, 5]))

    def generate_df(self, fleets_list, params):
        maps, planners, nRobots, holonomic, use_hotspots, nExperiences = self.get_unique_params(params)
        is_param_variable = self.get_variables(maps, planners, nRobots, holonomic, use_hotspots, nExperiences)
        assert is_param_variable.count(True) <=2, "Max allowed variable params is 2 to support the plotting using grouped plots"

        planner_names = ["RRT-Connect", "Lightning", "Thunder", "EGraphs", "RRT-Star"]
        kinematics = ["ReedShepp", "Holonomic"]
        sampling = ["Uniform", "Hotspots"]

        df = pd.DataFrame(columns=self.dataframe_columns)

        for i in range(len(fleets_list)):
            fleets = fleets_list[i]
            plan_times = []
            recall = []
            scratch = []
            max_exec_time = []

            for f in fleets:
                plan_times.append(f.total_planning_time)
                recall.append(f.nPlans_from_recall)
                scratch.append(f.nPlans_from_scratch)
                max_exec_time.append(f.get_highest_robot_mission_execution_time())

            newdf = pd.DataFrame(columns=self.dataframe_columns)
            newdf = newdf.fillna("-")
            newdf["Map"] = [params[i][0]] * len(fleets)
            newdf["Planner"] = [planner_names[params[i][1]]] * len(fleets)
            newdf["NumRobots"] = [params[i][2]] * len(fleets)
            newdf["Kinematics"] = [kinematics[params[i][3]]] * len(fleets)
            newdf["SamplingStrategy"] = [sampling[params[i][4]]] * len(fleets)
            newdf["NumExperience"] = [params[i][5]] * len(fleets)
            newdf["TotalPlanningTime"] = plan_times
            newdf["NumPlansFromRecall"] = recall
            newdf["NumPlansFromScratch"] = scratch
            newdf["MaxExecutionTime"] = max_exec_time

            df = df.append(newdf, ignore_index=True, sort=None)

        return df

    def plot_plans_from_recall(self, ax, nPlans_from_recall, nPlans_from_scratch, variable_names):
        recall_percent = np.round(np.array(nPlans_from_recall) / (np.array(nPlans_from_recall) + np.array(nPlans_from_scratch)) * 100.0, 1)
        scratch_percent = 100-recall_percent
        recall_percent = [str(np.round(p, 1))+"%" if p > 10 else None for p in recall_percent.tolist()]
        scratch_percent = [str(np.round(p, 1))+"%" if p > 10 else None for p in scratch_percent.tolist()]
        # Add some buffer ticks above the bars
        yticks = np.arange(0, nPlans_from_recall[0] + nPlans_from_scratch[0]+51, 50)
        self.plot_utils.custom_bar_plot(ax, variable_names, nPlans_from_recall, ylabel="Number of plans", value_color='k', value=recall_percent,
                        title="Plans generated from recall", yticks=yticks)
        # self.plot_utils.custom_bar_plot(ax, variable_names, nPlans_from_scratch, label="Scratch",
        #                 bottom=nPlans_from_recall, color='r', ylabel="Number of plans", value_color='k', value=scratch_percent,
        #                 title="Plans generated from recall", yticks=yticks)

    def plot_plans_from_recall_group(self, ax, nPlans_from_recall, nPlans_from_scratch, variable_names, variable_pos, params):
        param_sets = self.get_unique_params(params)
        nPlans_from_recall = np.array(nPlans_from_recall)
        nPlans_from_scratch = np.array(nPlans_from_scratch)

        nGroups = len(param_sets[variable_pos[0]])
        group_size = len(param_sets[variable_pos[1]])

        first_variable_names = []
        second_variable_names = []
        for v in variable_names:
            n1, n2 = v.split("-\n")
            if n1 not in first_variable_names:
                first_variable_names.append(n1)
            if n2 not in second_variable_names:
                second_variable_names.append(n2)

        bar_width = 0.25
        complete_bar_width = bar_width*group_size

        start_indices = np.arange(1, (nGroups+1)*(complete_bar_width+bar_width), (complete_bar_width+bar_width))
        start_indices = start_indices[0:nGroups]

        recall_percent = np.round(nPlans_from_recall / (nPlans_from_recall + nPlans_from_scratch) * 100.0, 1)
        scratch_percent = 100-recall_percent
        recall_percent = np.array([str(np.round(p, 1))+"%" if p > 10 else None for p in recall_percent.tolist()])
        scratch_percent = np.array([str(np.round(p, 1))+"%" if p > 10 else None for p in scratch_percent.tolist()])
        # Add some buffer ticks above the bars
        max_idx = np.argmax(nPlans_from_recall)
        yticks = np.arange(0, nPlans_from_recall[max_idx] + nPlans_from_scratch[max_idx]+51, 50)

        group_recall_vals = []
        group_scratch_vals = []
        group_recall_percent = []
        group_scratch_percent = []
        for i in range(nGroups):
            start = i*group_size
            res = np.zeros(group_size)
            res[:nPlans_from_recall[start:start+group_size].size] = nPlans_from_recall[start:start+group_size]
            group_recall_vals.append(res)

            res = np.zeros(group_size)
            res[:nPlans_from_scratch[start:start+group_size].size] = nPlans_from_scratch[start:start+group_size]
            group_scratch_vals.append(res)

            res = np.zeros(group_size).astype(str)
            res[:recall_percent[start:start+group_size].size] = recall_percent[start:start+group_size]
            group_recall_percent.append(res)

            res = np.zeros(group_size).astype(str)
            res[:scratch_percent[start:start+group_size].size] = scratch_percent[start:start+group_size]
            group_scratch_percent.append(res)

        group_recall_vals = np.array(group_recall_vals).T
        group_scratch_vals = np.array(group_scratch_vals).T
        group_recall_percent = np.array(group_recall_percent).T
        group_scratch_percent = np.array(group_scratch_percent).T

        res = [None]*group_size
        for i in range(group_size):
            res[i] = self.plot_utils.custom_bar_plot(ax, start_indices+(i*bar_width), group_recall_vals[i], barwidth=bar_width, label="Recall",
                        ylabel="Number of plans", value_color='k', value=group_recall_percent[i],
                        title="Plans generated from recall", yticks=yticks)
        # for i in range(group_size):
        #     self.plot_utils.custom_bar_plot(ax, start_indices+(i*bar_width), group_scratch_vals[i], barwidth=bar_width, label="Recall",
        #                 ylabel="Number of plans", value_color='k', value=group_scratch_percent[i], bottom=group_recall_vals[i],
        #                 title="Plans generated from recall", yticks=yticks, legend_loc='lower right')

        ax.set_xticks(start_indices - (bar_width/2.0) + (complete_bar_width / 2.0))
        ax.set_xticklabels(first_variable_names)
        ax.legend(res, second_variable_names, loc='lower right')

    def plot_planning_times(self, params, filename, use_LogScale=False):
        maps, planners, nRobots, holonomic, use_hotspots, nExperiences = self.get_unique_params(params)
        is_param_variable = self.get_variables(maps, planners, nRobots, holonomic, use_hotspots, nExperiences)

        assert is_param_variable.count(True) <=2, "Max allowed variable params is 2 to support the plotting using grouped plots"
        variable_pos = [i for i, val in enumerate(is_param_variable) if val]
        if len(variable_pos) < 2:
            variable_pos.append(None)

        fig = plt.figure(figsize=(15, 7.5))
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        fleets_list = []
        for p in params:
            fleets_list.append(self.data_loader.get_fleet_data(p[0], p[1], p[2], p[3], p[4], p[5]))

        fleet_ids = []
        total_plan_times = []
        nPlans_from_recall = []
        nPlans_from_scratch = []
        variable_names = []
        color_ids = []

        df = self.generate_df(fleets_list, params)

        for i in range(len(fleets_list)):
            variable_names.append(self.get_variable_name("", params[i], is_param_variable))
            fleets = fleets_list[i]
            color_ids.append(i/len(fleets_list))
            fleet_ids.append(np.arange(1, len(fleets) + 1, 1))
            plan_times = []
            recall = []
            scratch = []

            for f in fleets:
                plan_times.append(f.total_planning_time)
                recall.append(f.nPlans_from_recall)
                scratch.append(f.nPlans_from_scratch)

            total_plan_times.append(plan_times)
            nPlans_from_recall.append(sum(recall))
            nPlans_from_scratch.append(sum(scratch))

        # Plot planning times
        y_label = "Time in seconds"
        if use_LogScale:
            y_label += " ($log_{10}$ scale)"
        total_plan_times = np.log10(np.array(total_plan_times).T) if use_LogScale else np.array(total_plan_times).T
        # self.plot_utils.custom_box_plot(ax1, variable_names, total_plan_times,
        #                                 ylabel=y_label, title="Total planning time")
        hue = None
        if variable_pos[1] is not None:
            hue = self.dataframe_columns[variable_pos[1]]
        self.plot_utils.custom_grouped_box_plot(ax1, df, x=self.dataframe_columns[variable_pos[0]],
                                                y="TotalPlanningTime", hue=hue,
                                                ylabel=y_label, title="Total planning time")

        # for i in range(len(total_plan_times)):
        #     self.plot_utils.custom_line_plot(ax1, fleet_ids[i], total_plan_times[i], label=variable_names[i],
        #                     color=plt.cm.summer(color_ids[i]), xlabel="Fleet ID", ylabel="Time in seconds",
        #                     useLog10Scale=False, avg_line_col=plt.cm.summer(color_ids[i]), title="Total planning time")

        # Plot recall stats
        if variable_pos[1] is None:
            self.plot_plans_from_recall(ax2, nPlans_from_recall, nPlans_from_scratch, variable_names)
        else:
            self.plot_plans_from_recall_group(ax2, nPlans_from_recall, nPlans_from_scratch, variable_names, variable_pos, params)
        

        fig.suptitle(self.get_figure_title("Planning time stats", maps, planners, nRobots, holonomic, 
                                            use_hotspots, nExperiences, is_param_variable))

        # plot_name = os.path.join(self.get_directory_to_save_plots(fleets, assisted_sampling), "planning_times.svg")
        plt.savefig(filename, format='svg')

    def plot_throughput(self, ax, throughput, params, variable_names):
        max_throughput = np.max(throughput)
        param_sets = self.get_unique_params(params)
        self.plot_utils.custom_bar_plot(ax, variable_names, throughput, ylabel="Number of mobidik deliveries per hour",
                         title="Throughput", value_color='k', value=throughput, yticks=np.arange(0, max_throughput+11, 10))

    def plot_throughput_group(self, ax, throughput, params, variable_pos, variable_names):
        throughput = np.array(throughput)
        max_throughput = np.max(throughput)
        param_sets = self.get_unique_params(params)

        nGroups = len(param_sets[variable_pos[0]])
        group_size = len(param_sets[variable_pos[1]])

        first_variable_names = []
        second_variable_names = []
        for v in variable_names:
            n1, n2 = v.split("-\n")
            if n1 not in first_variable_names:
                first_variable_names.append(n1)
            if n2 not in second_variable_names:
                second_variable_names.append(n2)

        bar_width = 0.25
        complete_bar_width = bar_width*group_size

        start_indices = np.arange(1, (nGroups+1)*(complete_bar_width+bar_width), (complete_bar_width+bar_width))
        start_indices = start_indices[0:nGroups]

        group_vals = []
        for i in range(nGroups):
            start = i*group_size
            res = np.zeros(group_size)
            res[:throughput[start:start+group_size].size] = throughput[start:start+group_size]
            group_vals.append(res)
        group_vals = np.array(group_vals).T

        res = [None]*group_size
        for i in range(group_size):
            res[i] = self.plot_utils.custom_bar_plot(ax, start_indices+(i*bar_width), group_vals[i], barwidth=bar_width,
                            ylabel="Number of mobidik deliveries per hour",
                            title="Throughput", value_color='k', value=group_vals[i].astype(int), yticks=np.arange(0, max_throughput+11, 10))[0]

        ax.set_xticks(start_indices - (bar_width/2.0) + (complete_bar_width / 2.0))
        ax.set_xticklabels(first_variable_names)
        ax.legend(res, second_variable_names)


    def plot_exec_stats(self, params, filename):
        maps, planners, nRobots, holonomic, use_hotspots, nExperiences = self.get_unique_params(params)
        is_param_variable = self.get_variables(maps, planners, nRobots, holonomic, use_hotspots, nExperiences)
        assert is_param_variable.count(True) <=2, "Max allowed variable params is 2 to support the plotting using grouped plots"
        variable_pos = [i for i, val in enumerate(is_param_variable) if val]
        if len(variable_pos) < 2:
            variable_pos.append(None)

        fig = plt.figure(figsize=(15, 15))
        ax1 = fig.add_subplot(211)
        ax3 = fig.add_subplot(223)
        ax2 = fig.add_subplot(224)

        fleets_list = []
        for p in params:
            fleets_list.append(self.data_loader.get_fleet_data(p[0], p[1], p[2], p[3], p[4], p[5]))

        max_execution_times = []
        success_markers = []
        success_status = []
        throughput = []

        variable_names = []
        color_ids = []
        fleet_ids = []

        for i in range(len(fleets_list)):
            variable_names.append(self.get_variable_name("", params[i], is_param_variable))
            fleets = fleets_list[i]
            color_ids.append(i/len(fleets_list))
            fleet_ids.append(np.arange(1, len(fleets) + 1, 1))

            max_exec_time = np.zeros(len(fleets))
            success_m = ['X'] * len(fleets)
            success_s = np.zeros((len(fleets), 4))
            delivery_times = np.zeros_like(max_exec_time)
            num_deliveries = np.zeros_like(max_exec_time)

            for i, f in enumerate(fleets):
                max_exec_time[i] = f.get_highest_robot_mission_execution_time()
                percent, max_robots = f.get_percentage_of_mission_success()
                if np.allclose(percent, 100.0):
                    success_m[i] = "^"
                exec_status = f.get_mission_execution_stats()
                for num_success in range(4):
                    success_s[i, num_success] = exec_status[num_success]
                delivery_status = f.get_mobidik_delivery_status()
                num_deliveries[i] = delivery_status[0]
                if num_deliveries[i] > 0:
                    # Only consider delivery times if atleast one mobidik was delivered
                    delivery_times[i] = delivery_status[1]

            max_execution_times.append(max_exec_time)
            success_markers.append(success_m)
            success_status.append(success_s)
            # Throughtput per hour (3600 seconds)
            throughput.append(int(np.sum(num_deliveries)/np.sum(delivery_times) * 3600))

        # Plot mission execution times
        df = self.generate_df(fleets_list, params)
        max_execution_times = np.array(max_execution_times).T
        # self.plot_utils.custom_box_plot(ax1, variable_names, max_execution_times, horizontal=True,
        #                                 xlabel="Time in seconds", title="Complete fleet mission execution time")
        hue = None
        if variable_pos[1] is not None:
            hue = self.dataframe_columns[variable_pos[1]]
        self.plot_utils.custom_grouped_box_plot(ax1, df, x=self.dataframe_columns[variable_pos[0]], 
                                                y="MaxExecutionTime", hue=hue,
                                                ylabel="Time in seconds", title="Complete fleet mission execution time", 
                                                horizontal=True)

        # for i in range(len(max_execution_times)):
        #     c = plt.cm.jet(color_ids[i])
        #     self.plot_utils.custom_line_plot(ax1, fleet_ids[i], max_execution_times[i], label=variable_names[i],
        #                  color=c, xlabel="Fleet ID", ylabel="Time in seconds",
        #                  useLog10Scale=False, avg_line_col=c,
        #                  title="Complete fleet mission execution time")
            # for j, m in enumerate(success_markers[i]):
            #     ax1.scatter(fleet_ids[i][j], max_execution_times[i][j], marker=m, c=c, s=100)

        # Plot throughput
        if variable_pos[1] is None:
            self.plot_throughput(ax2, throughput, params, variable_names)
        else:
            self.plot_throughput_group(ax2, throughput, params, variable_pos, variable_names)

        # Plot Mission executions status
        all_success, all_success_percent = np.zeros(len(success_status)), np.zeros(len(success_status))
        one_failure, one_failure_percent = np.zeros_like(all_success), np.zeros_like(all_success)
        two_failure, two_failure_percent = np.zeros_like(all_success), np.zeros_like(all_success)
        all_failure, all_failure_percent = np.zeros_like(all_success), np.zeros_like(all_success)
        for i in range(len(success_status)):
            all_success[i] = np.sum(success_status[i][:, 3])
            one_failure[i] = np.sum(success_status[i][:, 2])
            two_failure[i] = np.sum(success_status[i][:, 1])
            all_failure[i] = np.sum(success_status[i][:, 0])
            num_robots = np.sum(success_status[i])
            all_success_percent[i] = np.round(all_success[i] / num_robots * 100, 1)
            one_failure_percent[i] = np.round(one_failure[i] / num_robots * 100, 1)
            two_failure_percent[i] = np.round(two_failure[i] / num_robots * 100, 1)
            all_failure_percent[i] = np.round(all_failure[i] / num_robots * 100, 1)

        all_success_percent = [str(np.round(p, 1))+"%" if p > 10 else None for p in all_success_percent.tolist()]
        one_failure_percent = [str(np.round(p, 1))+"%" if p > 10 else None for p in one_failure_percent.tolist()]
        two_failure_percent = [str(np.round(p, 1))+"%" if p > 10 else None for p in two_failure_percent.tolist()]
        all_failure_percent = [str(np.round(p, 1))+"%" if p > 10 else None for p in all_failure_percent.tolist()]

        max_idx = np.argmax(all_success)
        total_mission_count = all_success[max_idx] + one_failure[max_idx] + two_failure[max_idx] + all_failure[max_idx]
        # Add some buffer space abive the bars
        yticks = np.arange(0, total_mission_count + 50, 25)

        self.plot_utils.custom_horizontal_bar_plot(ax3, variable_names, all_success, label="All missions successful",
                         color=plt.cm.RdYlGn(1.0), ylabel="Number of robots", yticks=yticks, legend_loc='lower left',
                         title="Robot mission execution status", value_color='k', value=all_success_percent)
        self.plot_utils.custom_horizontal_bar_plot(ax3, variable_names, one_failure, label="Failed after delivering Mobidik", yticks=yticks, legend_loc='lower left',
                         bottom=all_success, color=plt.cm.RdYlGn(0.66), ylabel="Number of robots", value_color='k', value=one_failure_percent)
        self.plot_utils.custom_horizontal_bar_plot(ax3, variable_names, two_failure, label="Failed while transporting Mobidik", yticks=yticks, legend_loc='lower left',
                         bottom=one_failure+all_success, color=plt.cm.RdYlGn(0.33), ylabel="Number of robots", value_color='k', value=two_failure_percent)
        self.plot_utils.custom_horizontal_bar_plot(ax3, variable_names, all_failure, label="Failed before reaching Mobidik", yticks=yticks, legend_loc='lower left',
                         bottom=two_failure+one_failure+all_success, color=plt.cm.RdYlGn(0.0), ylabel="Number of robots", value_color='k', value=all_failure_percent)

        fig.suptitle(self.get_figure_title("Execution stats", maps, planners, nRobots, holonomic, 
                                            use_hotspots, nExperiences, is_param_variable))

        # plot_name = os.path.join(self.get_directory_to_save_plots(fleets, assisted_sampling), "planning_times.svg")
        plt.savefig(filename, format='svg')

    def plot_predictable_paths(self, ax, similarities, dissimilarities, variable_names, sim_thresh):
        similarities = np.array(similarities)
        dissimilarities = np.array(dissimilarities)

        sim_percentage = similarities / (similarities + dissimilarities) * 100.0
        dissim_percentage = 100.0 - sim_percentage
        sim_percentage = [str(np.round(p, 1))+"%" if p > 10 else None for p in sim_percentage.tolist()]
        dissim_percentage = [str(np.round(p, 1))+"%" if p > 10 else None for p in dissim_percentage.tolist()]

        # Plot the predictability of the paths
        self.plot_utils.custom_bar_plot(ax, variable_names, similarities, ylabel="Number of paths", value_color='k', value=sim_percentage,
                         title="Number of predictable paths with similarity threshold = {}".format(sim_thresh))
        # self.plot_utils.custom_bar_plot(ax, variable_names, dissimilarities, label="Number of non-similar paths",
        #                  bottom=similarities, color='r', ylabel="Number of paths", value_color='k', value=dissim_percentage)

    def plot_predictable_paths_group(self, ax, similarities, dissimilarities, variable_names, sim_thresh, variable_pos, params):
        param_sets = self.get_unique_params(params)
        similarities = np.array(similarities)
        dissimilarities = np.array(dissimilarities)

        nGroups = len(param_sets[variable_pos[0]])
        group_size = len(param_sets[variable_pos[1]])

        first_variable_names = []
        second_variable_names = []
        for v in variable_names:
            n1, n2 = v.split("-\n")
            if n1 not in first_variable_names:
                first_variable_names.append(n1)
            if n2 not in second_variable_names:
                second_variable_names.append(n2)

        bar_width = 0.25
        complete_bar_width = bar_width*group_size

        start_indices = np.arange(1, (nGroups+1)*(complete_bar_width+bar_width), (complete_bar_width+bar_width))
        start_indices = start_indices[0:nGroups]

        sim_percentage = similarities / (similarities + dissimilarities) * 100.0
        dissim_percentage = 100.0 - sim_percentage
        sim_percentage = np.array([str(np.round(p, 1))+"%" if p > 10 else None for p in sim_percentage.tolist()])
        dissim_percentage = np.array([str(np.round(p, 1))+"%" if p > 10 else None for p in dissim_percentage.tolist()])
        # Add some buffer ticks above the bars
        max_idx = np.argmax(similarities)
        yticks = np.arange(0, similarities[max_idx] + dissimilarities[max_idx]+51, 50)

        group_sim_vals = []
        group_dissim_vals = []
        group_sim_percent = []
        group_dissim_percent = []
        for i in range(nGroups):
            start = i*group_size
            res = np.zeros(group_size)
            res[:similarities[start:start+group_size].size] = similarities[start:start+group_size]
            group_sim_vals.append(res)

            res = np.zeros(group_size)
            res[:dissimilarities[start:start+group_size].size] = dissimilarities[start:start+group_size]
            group_dissim_vals.append(res)

            res = np.zeros(group_size).astype(str)
            res[:sim_percentage[start:start+group_size].size] = sim_percentage[start:start+group_size]
            group_sim_percent.append(res)

            res = np.zeros(group_size).astype(str)
            res[:dissim_percentage[start:start+group_size].size] = dissim_percentage[start:start+group_size]
            group_dissim_percent.append(res)

        group_sim_vals = np.array(group_sim_vals).T
        group_dissim_vals = np.array(group_dissim_vals).T
        group_sim_percent = np.array(group_sim_percent).T
        group_dissim_percent = np.array(group_dissim_percent).T

        res = [None]*group_size
        for i in range(group_size):
            res[i] = self.plot_utils.custom_bar_plot(ax, start_indices+(i*bar_width), group_sim_vals[i], barwidth=bar_width, label="Recall",
                        ylabel="Number of paths", value_color='k', value=group_sim_percent[i],
                        title="Predictability of paths with similarity threshold = {}".format(sim_thresh), yticks=yticks)
        # for i in range(group_size):
        #     self.plot_utils.custom_bar_plot(ax, start_indices+(i*bar_width), group_dissim_vals[i], barwidth=bar_width, label="Recall",
        #                 ylabel="Number of paths", value_color='k', value=group_dissim_percent[i], bottom=group_sim_vals[i],
        #                 title="Predictability of paths with similarity threshold = {}".format(sim_thresh), yticks=yticks,
        #                 legend_loc='lower right')

        ax.set_xticks(start_indices - (bar_width/2.0) + (complete_bar_width / 2.0))
        ax.set_xticklabels(first_variable_names)
        ax.legend(res, second_variable_names, loc='lower right')

    def plot_path_quality_stats(self, params, filename, sim_thresh=0.3):
        maps, planners, nRobots, holonomic, use_hotspots, nExperiences = self.get_unique_params(params)
        is_param_variable = self.get_variables(maps, planners, nRobots, holonomic, use_hotspots, nExperiences)
        assert is_param_variable.count(True) <=2, "Max allowed variable params is 2 to support the plotting using grouped plots"
        variable_pos = [i for i, val in enumerate(is_param_variable) if val]
        if len(variable_pos) < 2:
            variable_pos.append(None)

        fig = plt.figure(figsize=(15, 7.5))
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        fleets_list = []
        for p in params:
            fleets_list.append(self.data_loader.get_fleet_data(p[0], p[1], p[2], p[3], p[4], p[5]))

        similarities = []
        dissimilarities = []
        path_suboptimalities = []

        variable_names = []
        color_ids = []
        fleet_ids = []

        columns = ["Map", "Planner", "NumRobots", "Kinematics", "SamplingStrategy", "NumExperience", "RobotID", "Suboptimality"]
        subopt_df = pd.DataFrame(columns=columns)

        nTests = 0
        for f_id in range(len(fleets_list)):
            variable_names.append(self.get_variable_name("", params[f_id], is_param_variable))
            fleets = fleets_list[f_id]
            color_ids.append(f_id/len(fleets_list))
            fleet_ids.append(np.arange(1, len(fleets) + 1, 1))
            assisted_sampling = params[f_id][4]

            # print("Find similarities for:", variable_names[-1].replace('\n', ''))
            sim, nTests = np.random.randint(150, 250), 250
            sim, nTests = self.dwt.determine_num_similar_paths(fleets, assisted_sampling, similarity_threshold=sim_thresh)
            similarities.append(np.sum(sim))
            dissimilarities.append(np.sum((np.ones_like(sim) * nTests) - sim))

            # Get the path suboptimalities of all the robot missions in all fleet trials
            sub_optimalities = np.zeros((len(fleets), fleets[0].nRobots))
            robot_ids = np.zeros((len(fleets), fleets[0].nRobots))
            for i, f in enumerate(fleets):
                for j, m in enumerate(f.robot_missions):
                    sub_optimalities[i, j] = np.clip(m.complete_path_length / m.complete_optimal_path_length, 1.0, 100.0)
                    robot_ids[i, j] = j
            path_suboptimalities.append(np.reshape(sub_optimalities, sub_optimalities.size))

            planner_names = ["RRT-Connect", "Lightning", "Thunder", "EGraphs", "RRT-Star"]
            kinematics = ["ReedShepp", "Holonomic"]
            sampling = ["Uniform", "Hotspots"]

            newdf = pd.DataFrame(columns=columns)
            newdf = newdf.fillna("-")
            newdf["Map"] = [params[f_id][0]] * sub_optimalities.size
            newdf["Planner"] = [planner_names[params[f_id][1]]] * sub_optimalities.size
            newdf["NumRobots"] = [params[f_id][2]] * sub_optimalities.size
            newdf["Kinematics"] = [kinematics[params[f_id][3]]] * sub_optimalities.size
            newdf["SamplingStrategy"] = [sampling[params[f_id][4]]] * sub_optimalities.size
            newdf["NumExperience"] = [params[f_id][5]] * sub_optimalities.size
            newdf["Suboptimality"] = np.reshape(sub_optimalities, sub_optimalities.size)
            newdf["RobotID"] = np.reshape(robot_ids, robot_ids.size).astype(int)
            subopt_df = subopt_df.append(newdf, ignore_index=True, sort=None)

        # Plot the suboptimality of the paths
        path_suboptimalities = np.array(path_suboptimalities).T
        if variable_pos[1] is None:
            self.plot_utils.custom_box_plot(ax1, variable_names, path_suboptimalities,
                                        ylabel="Suboptimality ratio", title="Path Suboptimality")
        else:
            hue = None
            if variable_pos[1] is not None:
                hue = self.dataframe_columns[variable_pos[1]]
            self.plot_utils.custom_grouped_box_plot(ax1, subopt_df, x=columns[variable_pos[0]], 
                                                    y="Suboptimality", hue=hue,
                                                    ylabel="Suboptimality ratio", title="Path Suboptimality")

        if variable_pos[1] is None:
            self.plot_predictable_paths(ax2, similarities, dissimilarities, variable_names, sim_thresh)
        else:
            self.plot_predictable_paths_group(ax2, similarities, dissimilarities, variable_names, sim_thresh, variable_pos, params)

        fig.suptitle(self.get_figure_title("Path quality stats", maps, planners, nRobots, holonomic, 
                                            use_hotspots, nExperiences, is_param_variable))
        plt.savefig(filename, format='svg')

    def get_directory_to_save_plots(self, fleets, assisted_sampling):
        if self.save_path is None:
            sampling_name = "UsingHotspots" if assisted_sampling else "Uniform"
            kinematics = "Holonomic" if self.get_holonomic(fleets) else "ReedsSheep"
            self.save_path = os.path.abspath(os.path.split(os.path.abspath(sys.argv[0]))[0]  + "/../../generated/executionData/")
            self.save_path = os.path.join(self.save_path, self.get_map_name(fleets))
            self.save_path = os.path.join(self.save_path, self.get_planner_name(fleets))
            self.save_path = os.path.join(self.save_path, str(self.get_nRobots(fleets))+"_Robots")
            self.save_path = os.path.join(self.save_path, kinematics)
            self.save_path = os.path.join(self.save_path, sampling_name)
            self.save_path = os.path.join(self.save_path, str(self.nExperiences)+"_TrainingExperiences/Plots")

        # Make the directory if it does not exist
        try:
            os.makedirs(self.save_path)
        except OSError as exc:
            if exc.errno ==errno.EEXIST and os.path.isdir(self.save_path):
                pass
            else:
                raise "Could not create directory to save plots at {}".format(self.save_path)

        return self.save_path


def main():
    mla = MultiLogAnalyzer()

    # Order: maps, planners, nRobots, holonomic, use_hotspots, nExperiences
    exp_results_dir = os.path.abspath(os.path.split(os.path.abspath(sys.argv[0]))[0]  + "/../../generated/ExperimentResults/")

    # Experiment - 1
    mla.load_all_fleets(["BRSU_Floor0"], [0, 1, 2, 3, 4], [5], [True], [True], [25])
    params = [
              ["BRSU_Floor0", 0, 5, True, True, 25],
              ["BRSU_Floor0", 4, 5, True, True, 25],
              ["BRSU_Floor0", 1, 5, True, True, 25],
              ["BRSU_Floor0", 2, 5, True, True, 25],
              ["BRSU_Floor0", 3, 5, True, True, 25]
              ]
    mla.plot_planning_times(params, os.path.join(exp_results_dir, "Experiment1/Planning.svg"))
    mla.plot_exec_stats(params, os.path.join(exp_results_dir, "Experiment1/Execution.svg"))
    mla.plot_path_quality_stats(params, os.path.join(exp_results_dir, "Experiment1/PathQuality.svg"))

    # Experiment - 2
    mla.load_all_fleets(["BRSU_Floor0"], [1, 2, 3], [5, 7, 10], [True], [True], [25])
    params = sorted([
              ["BRSU_Floor0", 1, 5, True, True, 25],
              ["BRSU_Floor0", 2, 5, True, True, 25],
              ["BRSU_Floor0", 3, 5, True, True, 25],
              ["BRSU_Floor0", 1, 7, True, True, 25],
              ["BRSU_Floor0", 2, 7, True, True, 25],
              ["BRSU_Floor0", 3, 7, True, True, 25],
              ["BRSU_Floor0", 1, 10, True, True, 25],
              ["BRSU_Floor0", 2, 10, True, True, 25],
              ["BRSU_Floor0", 3, 10, True, True, 25]
              ])
    mla.plot_planning_times(params, os.path.join(exp_results_dir, "Experiment2/Planning.svg"))
    mla.plot_exec_stats(params, os.path.join(exp_results_dir, "Experiment2/Execution.svg"))
    mla.plot_path_quality_stats(params, os.path.join(exp_results_dir, "Experiment2/PathQuality.svg"))

    # Experiment - 3
    mla.load_all_fleets(["BRSU_Floor0"], [1, 2, 3], [5], [True], [True], [10, 25, 50])
    mla.load_all_fleets(["BRSU_Floor0"], [1, 2], [5], [True], [True], [100])
    params = sorted([
              ["BRSU_Floor0", 1, 5, True, True, 10],
              ["BRSU_Floor0", 2, 5, True, True, 10],
              ["BRSU_Floor0", 3, 5, True, True, 10],
              ["BRSU_Floor0", 1, 5, True, True, 25],
              ["BRSU_Floor0", 2, 5, True, True, 25],
              ["BRSU_Floor0", 3, 5, True, True, 25],
              ["BRSU_Floor0", 1, 5, True, True, 50],
              ["BRSU_Floor0", 2, 5, True, True, 50],
              ["BRSU_Floor0", 3, 5, True, True, 50],
              ["BRSU_Floor0", 1, 5, True, True, 100],
              ["BRSU_Floor0", 2, 5, True, True, 100],
              ])
    mla.plot_planning_times(params, os.path.join(exp_results_dir, "Experiment3/Planning.svg"))
    mla.plot_exec_stats(params, os.path.join(exp_results_dir, "Experiment3/Execution.svg"))
    mla.plot_path_quality_stats(params, os.path.join(exp_results_dir, "Experiment3/PathQuality.svg"))

    # Experiment - 4
    mla.load_all_fleets(["BRSU_Floor0"], [1, 2], [5], [True, False], [True], [25])
    params = sorted([
              ["BRSU_Floor0", 1, 5, True, True, 25],
              ["BRSU_Floor0", 2, 5, True, True, 25],
              ["BRSU_Floor0", 1, 5, False, True, 25],
              ["BRSU_Floor0", 2, 5, False, True, 25]
              ])
    mla.plot_planning_times(params, os.path.join(exp_results_dir, "Experiment4/Planning.svg"))
    mla.plot_exec_stats(params, os.path.join(exp_results_dir, "Experiment4/Execution.svg"))
    mla.plot_path_quality_stats(params, os.path.join(exp_results_dir, "Experiment4/PathQuality.svg"))

    # Experiment - 5
    mla.load_all_fleets(["BRSU_Floor0"], [1, 2, 3], [5], [True], [True, False], [25])
    params = sorted([
              ["BRSU_Floor0", 1, 5, True, True, 25],
              ["BRSU_Floor0", 2, 5, True, True, 25],
              ["BRSU_Floor0", 3, 5, True, True, 25],
              ["BRSU_Floor0", 1, 5, True, False, 25],
              ["BRSU_Floor0", 2, 5, True, False, 25],
              ["BRSU_Floor0", 3, 5, True, False, 25]
              ])
    mla.plot_planning_times(params, os.path.join(exp_results_dir, "Experiment5/Planning.svg"))
    mla.plot_exec_stats(params, os.path.join(exp_results_dir, "Experiment5/Execution.svg"))
    mla.plot_path_quality_stats(params, os.path.join(exp_results_dir, "Experiment5/PathQuality.svg"))

    # Experiment - 6
    mla.load_all_fleets(["BRSU_Floor0", "AGP_Basement", "AGP_Floor4", "hospital_stage"], [0, 1, 2, 3], [5], [True], [True], [25])
    params = sorted([
              ["BRSU_Floor0", 0, 5, True, True, 25],
              ["BRSU_Floor0", 1, 5, True, True, 25],
              ["BRSU_Floor0", 2, 5, True, True, 25],
              ["BRSU_Floor0", 3, 5, True, True, 25],
              ["AGP_Basement", 0, 5, True, True, 25],
              ["AGP_Basement", 1, 5, True, True, 25],
              ["AGP_Basement", 2, 5, True, True, 25],
              ["AGP_Basement", 3, 5, True, True, 25],
              ["AGP_Floor4", 0, 5, True, True, 25],
              ["AGP_Floor4", 1, 5, True, True, 25],
              ["AGP_Floor4", 2, 5, True, True, 25],
              ["AGP_Floor4", 3, 5, True, True, 25],
              ["hospital_stage", 0, 5, True, True, 25],
              ["hospital_stage", 1, 5, True, True, 25],
              ["hospital_stage", 2, 5, True, True, 25],
              ["hospital_stage", 3, 5, True, True, 25]
              ])
    mla.plot_planning_times(params, os.path.join(exp_results_dir, "Experiment6/Planning.svg"))
    mla.plot_exec_stats(params, os.path.join(exp_results_dir, "Experiment6/Execution.svg"))
    mla.plot_path_quality_stats(params, os.path.join(exp_results_dir, "Experiment6/PathQuality.svg"))

if __name__ == "__main__":
    main()
