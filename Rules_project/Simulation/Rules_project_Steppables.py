from cc3d.core.PySteppables import *
import copy
import inspect
import importlib.util
import json
import math
import random
import re
from pathlib import Path

GENERATED_CODE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()

COMPILED_RULES = [{'id': '1',
  'target': 'FungusYeast',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'field_name': 'FungalSignal',
             'secret_mode': 'secreteInsideCellAtCOM',
             'amount': 0.01,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '1_copy',
  'target': 'AttachedFungus',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'field_name': 'FungalSignal',
             'secret_mode': 'secreteInsideCellAtCOM',
             'amount': 0.01,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': 'host_associated_cue_source',
  'target': 'HostCell',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'field_name': 'HostAssociatedCue',
             'secret_mode': 'secreteInsideCellAtCOM',
             'amount': 0.0005,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '2',
  'target': 'FungusYeast',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'Environment',
                      'params': {'operator': '>',
                                 'threshold': 0.03,
                                 'field_name': 'HostAssociatedCue',
                                 'sampling_mode': 'cell_average'}},
             'field_name': 'HostAssociatedCue',
             'secret_mode': 'uptakeInsideCell',
             'amount': 0.0015,
             'relative_uptake': 0.006,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '3',
  'target': 'HostCell',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 350,
                                 'sub_condition': {'condition_type': 'Logic_AND',
                                                   'params': {'conditions': [{'condition_type': 'Logic_OR',
                                                                              'params': {'conditions': [{'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'FungusYeast',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'AttachedFungus',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaTip',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaSegment',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaRoot',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}}]}},
                                                                             {'condition_type': 'Logic_OR',
                                                                              'params': {'conditions': [{'condition_type': 'Environment',
                                                                                                         'params': {'field_name': 'FungalSignal',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0.05,
                                                                                                                    'sampling_mode': 'boundary_max'}},
                                                                                                        {'condition_type': 'Environment',
                                                                                                         'params': {'field_name': 'DamageFactor',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0.04,
                                                                                                                    'sampling_mode': 'boundary_max'}}]}}]}}}},
             'field_name': 'DamageFactor',
             'secret_mode': 'secreteInsideCellAtBoundary',
             'amount': 0.0005,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '4',
  'target': 'HostCell',
  'behaviour': 'differentiate',
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 450,
                                 'sub_condition': {'condition_type': 'Logic_AND',
                                                   'params': {'conditions': [{'condition_type': 'Logic_OR',
                                                                              'params': {'conditions': [{'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'AttachedFungus',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaTip',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaSegment',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaRoot',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}}]}},
                                                                             {'condition_type': 'Logic_OR',
                                                                              'params': {'conditions': [{'condition_type': 'Environment',
                                                                                                         'params': {'field_name': 'FungalSignal',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0.08,
                                                                                                                    'sampling_mode': 'boundary_max'}},
                                                                                                        {'condition_type': 'Environment',
                                                                                                         'params': {'field_name': 'DamageFactor',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0.08,
                                                                                                                    'sampling_mode': 'cell_average'}}]}}]}}}},
             'mode': 'type_switch',
             'new_type': 'DamagedHostCell'}],
  'frequency': 10,
  'once': False,
  'debug': False},
 {'id': '8',
  'target': 'FungusYeast',
  'behaviour': 'death',
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 800,
                                 'sub_condition': {'condition_type': 'Environment',
                                                   'params': {'field_name': 'DamageFactor',
                                                              'operator': '>',
                                                              'threshold': 0.15,
                                                              'sampling_mode': 'cell_average'}}}},
             'mode': 'apoptosis',
             'model': 'shrink_model',
             'shrink_rate': 0.98,
             'terminal_volume': 0.0,
             'color_change': 'grey'}],
  'frequency': 5,
  'once': True,
  'debug': False},
 {'id': '9',
  'target': 'AttachedFungus',
  'behaviour': 'death',
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 1200,
                                 'sub_condition': {'condition_type': 'Environment',
                                                   'params': {'field_name': 'DamageFactor',
                                                              'operator': '>',
                                                              'threshold': 0.25,
                                                              'sampling_mode': 'cell_average'}}}},
             'mode': 'apoptosis',
             'model': 'shrink_model',
             'shrink_rate': 0.99,
             'terminal_volume': 0.0,
             'color_change': 'grey'}],
  'frequency': 5,
  'once': True,
  'debug': False},
 {'id': '5',
  'target': 'FungusYeast',
  'behaviour': 'chemotaxis',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'mode': 'chemotaxis',
             'field_name': 'HostAssociatedCue',
             'lambda': 260.0,
             'formula': 'Standard',
             'coef': None,
             'target_strategy': 'break',
             'mode_param': 'field=HostAssociatedCue,lambda=DYNAMIC,formula=Standard'}],
  'frequency': 10,
  'once': False,
  'debug': False},
 {'id': '6',
  'target': 'FungusYeast',
  'behaviour': 'differentiate',
  'cases': [{'when': {'condition_type': 'Contact',
                      'params': {'operator': '>', 'threshold': 0, 'target_type': 'HostCell'}},
             'mode': 'type_switch',
             'new_type': 'AttachedFungus'}],
  'frequency': 20,
  'once': False,
  'debug': False},
 {'id': '7',
  'target': 'AttachedFungus',
  'behaviour': 'chemotaxis',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'mode': 'chemotaxis',
             'field_name': 'HostAssociatedCue',
             'lambda': 0.0,
             'formula': 'Standard',
             'coef': None,
             'target_strategy': 'break',
             'mode_param': 'field=HostAssociatedCue,lambda=DYNAMIC,formula=Standard'}],
  'frequency': 10,
  'once': False,
  'debug': False},
 {'id': '10',
  'target': 'FungusYeast',
  'behaviour': 'differentiate',
  'cases': [{'when': {'condition_type': 'Logic_AND',
                      'params': {'conditions': [{'condition_type': 'TimeWindow',
                                                 'params': {'start': 300, 'end': 1000000000}},
                                                {'condition_type': 'Environment',
                                                 'params': {'field_name': 'HostAssociatedCue',
                                                            'operator': '>',
                                                            'threshold': 0.2,
                                                            'sampling_mode': 'cell_average'}},
                                                {'condition_type': 'State',
                                                 'params': {'regulator': 'division_count',
                                                            'operator': '<',
                                                            'threshold': 3}},
                                                {'condition_type': 'Probability', 'params': {'p': 0.03}},
                                                {'condition_type': 'Logic_NOT',
                                                 'params': {'conditions': [{'condition_type': 'Contact',
                                                                            'params': {'target_type': 'HostCell',
                                                                                       'operator': '>',
                                                                                       'threshold': 0}}]}}]}},
             'mode': 'division',
             'parent_type': 'FungusYeast',
             'child_type': 'FungusYeast',
             'volume_ratio': 0.5,
             'inheritance_strategy': 'total',
             'state_key': 'division_count',
             'placement': {'type': 'random'}}],
  'frequency': 100,
  'once': False,
  'debug': False},
 {'id': '11',
  'target': 'AttachedFungus',
  'behaviour': 'differentiate',
  'frequency': 5,
  'once': False,
  'debug': False,
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 10,
                                 'sub_condition': {'condition_type': 'Logic_OR',
                                                   'params': {'conditions': [{'condition_type': 'Contact',
                                                                              'params': {'target_type': 'HostCell',
                                                                                         'operator': '>',
                                                                                         'threshold': 0}},
                                                                             {'condition_type': 'Contact',
                                                                              'params': {'target_type': 'DamagedHostCell',
                                                                                         'operator': '>',
                                                                                         'threshold': 0}},
                                                                             {'condition_type': 'Contact',
                                                                              'params': {'target_type': 'InterstitialSpace',
                                                                                         'operator': '>',
                                                                                         'threshold': 0}}]}}}},
             'mode': 'type_switch',
             'new_type': 'HyphaRoot'}]},
 {'id': '11_root_seed_tip',
  'target': 'HyphaRoot',
  'behaviour': 'compartmentalize',
  'frequency': 1,
  'once': True,
  'debug': False,
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'action': 'extend_chain',
             'segment_type': 'HyphaRoot',
             'tip_type': 'HyphaTip',
             'root_type': 'HyphaRoot',
             'direction_mode': 'toward_nearest_type',
             'direction_target_types': ['HostCell', 'DamagedHostCell', 'InterstitialSpace'],
             'direction_search_radius': 80,
             'dx': -1.0,
             'dy': 0.0,
             'dz': 0.0,
             'extension_interval': 1,
             'step_length': 1.0,
             'max_length': 80,
             'search_radius': 1,
             'use_fpp_link': True,
             'link_lambda': 40.0,
             'target_distance': 1.0,
             'max_distance': 3.0,
             'branch_probability': 0.0,
             'allow_occupied_site': True,
             'replace_target_types': ['HostCell', 'DamagedHostCell', 'InterstitialSpace'],
             'internal_contact_energy': 2.0,
             'internal_neighbor_order': 4,
             'site_selection_mode': 'front_replace_first',
             'direction_noise': 0.0,
             'fpp_activation_energy': 0.0,
             'max_junctions': 1,
             'fpp_neighbor_order': 1,
             'delay_first_extension': False,
             'initial_extension_delay': 0,
             'fpp_diagnostics': False,
             'fpp_diagnostic_interval': 200,
             'debug': False,
             'tip_seed_radius': 1,
             'max_branch_length': 0,
             'branch_length_metric': 'branch_length',
             'start_new_branch': False,
             'allow_same_type_internal_link': False,
             'visualize_fpp_link': False,
             'max_active_tips_per_cluster': 0,
             'bridge_to_tip': False,
             'require_replace_site': False,
             'root_link_max_junctions': 1}]},
 {'id': '12',
  'target': 'HyphaTip',
  'behaviour': 'compartmentalize',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'action': 'extend_chain',
             'segment_type': 'HyphaSegment',
             'tip_type': 'HyphaTip',
             'root_type': 'HyphaRoot',
             'direction_mode': 'inherit_orientation',
             'direction_target_types': ['HostCell', 'DamagedHostCell', 'InterstitialSpace'],
             'dx': -1.0,
             'dy': 0.0,
             'dz': 0.0,
             'extension_interval': 5,
             'step_length': 1.0,
             'max_length': 80,
             'search_radius': 1,
             'use_fpp_link': True,
             'link_lambda': 40.0,
             'target_distance': 1.0,
             'max_distance': 3.0,
             'branch_probability': 0.0,
             'allow_occupied_site': True,
             'replace_target_types': ['HostCell', 'DamagedHostCell', 'InterstitialSpace'],
             'internal_contact_energy': 2.0,
             'internal_neighbor_order': 4,
             'site_selection_mode': 'front_replace_first',
             'direction_noise': 0.0,
             'fpp_activation_energy': 0.0,
             'max_junctions': 2,
             'fpp_neighbor_order': 1,
             'delay_first_extension': False,
             'initial_extension_delay': 0,
             'fpp_diagnostics': False,
             'fpp_diagnostic_interval': 200,
             'debug': False,
             'tip_seed_radius': 1,
             'max_branch_length': 6,
             'branch_length_metric': 'branch_length',
             'cluster_tip_selection': 'random_one_per_cluster',
             'single_tip_per_cluster': True,
             'tip_selection_group': 'hypha_extension',
             'start_new_branch': False,
             'visualize_fpp_link': False,
             'bridge_to_tip': False,
             'require_replace_site': False,
             'max_active_tips_per_cluster': 0,
             'compartment_single_extend_per_branch': False,
             'root_link_max_junctions': 1}],
  'frequency': 10,
  'once': False,
  'debug': False},
 {'id': '12_branch',
  'target': 'HyphaSegment',
  'behaviour': 'compartmentalize',
  'frequency': 1000000,
  'once': False,
  'debug': False,
  'cases': [{'action': 'branch',
             'segment_type': 'HyphaSegment',
             'tip_type': 'HyphaTip',
             'direction_mode': 'stored_vector',
             'branch_angle_degrees': 45,
             'branch_angle_jitter_degrees': 15,
             'branch_probability': 0.0,
             'max_branches_per_segment': 3,
             'max_branch_length': 6,
             'single_branch_per_cluster': True,
             'compartment_single_extend_per_branch': False,
             'use_fpp_link': False,
             'debug': False,
             'when': {'condition_type': 'TRUE', 'params': {}},
             'visualize_fpp_link': False}]},
 {'id': '13',
  'target': 'HyphaTip',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'field_name': 'FungalSignal',
             'secret_mode': 'secreteInsideCellAtCOM',
             'amount': 0.02,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '14',
  'target': 'HyphaSegment',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'field_name': 'FungalSignal',
             'secret_mode': 'secreteInsideCellAtCOM',
             'amount': 0.006,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '15',
  'target': 'HyphaTip',
  'behaviour': 'death',
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 1000,
                                 'sub_condition': {'condition_type': 'Environment',
                                                   'params': {'field_name': 'DamageFactor',
                                                              'operator': '>',
                                                              'threshold': 0.35,
                                                              'sampling_mode': 'cell_average'}}}},
             'mode': 'apoptosis',
             'model': 'shrink_model',
             'shrink_rate': 0.99,
             'terminal_volume': 0.0,
             'color_change': 'grey'}],
  'frequency': 10,
  'once': False,
  'debug': False},
 {'id': '17',
  'target': 'DamagedHostCell',
  'behaviour': 'differentiate',
  'cases': [{'when': {'condition_type': 'Duration',
                      'params': {'threshold_mcs': 800,
                                 'sub_condition': {'condition_type': 'Logic_AND',
                                                   'params': {'conditions': [{'condition_type': 'Logic_OR',
                                                                              'params': {'conditions': [{'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaTip',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaSegment',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}},
                                                                                                        {'condition_type': 'Contact',
                                                                                                         'params': {'target_type': 'HyphaRoot',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0}}]}},
                                                                             {'condition_type': 'Logic_OR',
                                                                              'params': {'conditions': [{'condition_type': 'Environment',
                                                                                                         'params': {'field_name': 'DamageFactor',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0.14,
                                                                                                                    'sampling_mode': 'cell_average'}},
                                                                                                        {'condition_type': 'Environment',
                                                                                                         'params': {'field_name': 'FungalSignal',
                                                                                                                    'operator': '>',
                                                                                                                    'threshold': 0.14,
                                                                                                                    'sampling_mode': 'boundary_max'}}]}}]}}}},
             'mode': 'type_switch',
             'new_type': 'InterstitialSpace'}],
  'frequency': 10,
  'once': False,
  'debug': False},
 {'id': '18',
  'target': 'DamagedHostCell',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'Environment',
                      'params': {'field_name': 'FungalSignal',
                                 'operator': '>',
                                 'threshold': 0.035,
                                 'sampling_mode': 'boundary_max'}},
             'field_name': 'DamageFactor',
             'secret_mode': 'secreteInsideCellAtBoundary',
             'amount': 0.0007,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False},
 {'id': '16_branch_hypha_segment',
  'target': 'HyphaSegment',
  'behaviour': 'compartmentalize',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'action': 'branch_chain',
             'segment_type': 'HyphaSegment',
             'tip_type': 'HyphaTip',
             'root_type': 'HyphaRoot',
             'branch_source_filter': 'root_child',
             'branch_selection_group': 'hypha_branch',
             'direction_mode': 'inherit_orientation',
             'direction_target_types': ['HostCell', 'DamagedHostCell', 'InterstitialSpace'],
             'dx': -1.0,
             'dy': 0.0,
             'dz': 0.0,
             'extension_interval': 35,
             'step_length': 1.0,
             'max_length': 80,
             'search_radius': 1,
             'use_fpp_link': True,
             'link_lambda': 40.0,
             'target_distance': 1.0,
             'max_distance': 3.0,
             'branch_probability': 0.025,
             'allow_occupied_site': True,
             'replace_target_types': ['HostCell', 'DamagedHostCell', 'InterstitialSpace'],
             'internal_contact_energy': 2.0,
             'internal_neighbor_order': 4,
             'site_selection_mode': 'front_replace_first',
             'direction_noise': 0.0,
             'fpp_activation_energy': 0.0,
             'max_junctions': 2,
             'fpp_neighbor_order': 1,
             'delay_first_extension': False,
             'initial_extension_delay': 0,
             'fpp_diagnostics': False,
             'fpp_diagnostic_interval': 200,
             'debug': False,
             'tip_seed_radius': 1,
             'max_branch_length': 6,
             'branch_length_metric': 'branch_length',
             'max_branches_per_segment': 2,
             'branch_interval': 260,
             'branch_angle_min_degrees': 30.0,
             'branch_angle_max_degrees': 60.0,
             'branch_direction_mode': 'angle',
             'branch_step_length': 1.0,
             'branch_search_radius': 1,
             'visualize_fpp_link': False,
             'max_active_tips_per_cluster': 3,
             'single_branch_per_cluster': True,
             'start_new_branch': True,
             'bridge_to_tip': False,
             'require_replace_site': False,
             'compartment_single_extend_per_branch': False,
             'root_link_max_junctions': 1}],
  'frequency': 80,
  'once': False,
  'debug': False},
 {'id': '14_root_signal',
  'target': 'HyphaRoot',
  'behaviour': 'secrete/uptake',
  'cases': [{'when': {'condition_type': 'TRUE', 'params': {}},
             'field_name': 'FungalSignal',
             'secret_mode': 'secreteInsideCellAtCOM',
             'amount': 0.02,
             'relative_uptake': 0.0,
             'contact_types': [],
             'total_count': False}],
  'frequency': 1,
  'once': False,
  'debug': False}]
COMPILED_SETTINGS = {'execution_semantics': 'snapshot'}
COMPILED_CELLTYPE_PARAMS = {'HostCell': {'targetVolume': 160.0, 'lambdaVolume': 1.5, 'should_initialize': True, 'initial_count': 1},
 'FungusYeast': {'targetVolume': 18.0, 'lambdaVolume': 8.0, 'should_initialize': True, 'initial_count': 1},
 'AttachedFungus': {'targetVolume': 18.0, 'lambdaVolume': 18.0, 'should_initialize': False, 'initial_count': 5},
 'HyphaTip': {'targetVolume': 12.0, 'lambdaVolume': 8.0, 'should_initialize': False, 'initial_count': 0},
 'HyphaSegment': {'targetVolume': 8.0, 'lambdaVolume': 8.0, 'should_initialize': False, 'initial_count': 0},
 'DamagedHostCell': {'targetVolume': 160.0, 'lambdaVolume': 1.5, 'should_initialize': False, 'initial_count': 0},
 'InterstitialSpace': {'targetVolume': 8.0, 'lambdaVolume': 10.0, 'should_initialize': False, 'initial_count': 0},
 'HyphaRoot': {'targetVolume': 12.0, 'lambdaVolume': 18.0, 'should_initialize': False, 'initial_count': 0}}
COMPILED_FIELD_PARAMS = {'DamageFactor': {'solver': 'DiffusionSolverFE',
                  'diffusion_constant': 0.03,
                  'decay_constant': 0.001,
                  'initial_expression': '0.0',
                  'python_secretion': True,
                  'boundary_conditions': {'X': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0},
                                          'Y': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0}},
                  'chemotaxis': []},
 'FungalSignal': {'solver': 'DiffusionSolverFE',
                  'diffusion_constant': 0.02,
                  'decay_constant': 0.001,
                  'initial_expression': '0.0',
                  'python_secretion': True,
                  'boundary_conditions': {'X': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0},
                                          'Y': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0}},
                  'chemotaxis': []},
 'Nutrient': {'solver': 'DiffusionSolverFE',
              'diffusion_constant': 0.01,
              'decay_constant': 0.0001,
              'initial_expression': '  0.05 + 0.95/(1 + exp((x-128)/6))\n\n',
              'python_secretion': True,
              'boundary_conditions': {'X': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0},
                                      'Y': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0}},
              'chemotaxis': []},
 'HostAssociatedCue': {'solver': 'DiffusionSolverFE',
                       'diffusion_constant': 0.08,
                       'decay_constant': 8e-05,
                       'initial_expression': '0.08 + 0.42*(1 - x/255.0)',
                       'python_secretion': True,
                       'boundary_conditions': {'X': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0},
                                               'Y': {'type': 'ConstantDerivative', 'min_val': 0.0, 'max_val': 0.0}},
                       'chemotaxis': [{'cell_type': 'FungusYeast',
                                       'lambda': '0.0',
                                       'mode': 'simple',
                                       'sat_coef': '0.0',
                                       'rule_managed': True},
                                      {'cell_type': 'AttachedFungus',
                                       'lambda': '0.0',
                                       'mode': 'simple',
                                       'sat_coef': '0.0',
                                       'rule_managed': True}]}}


class Candida_albicans_zebrafishSteppable(MitosisSteppableBase):
    def __init__(self, frequency=1):
        MitosisSteppableBase.__init__(self, frequency)
        self.rules = copy.deepcopy(COMPILED_RULES)
        self.settings = copy.deepcopy(COMPILED_SETTINGS)
        self.celltype_params = copy.deepcopy(COMPILED_CELLTYPE_PARAMS)
        self.field_params = copy.deepcopy(COMPILED_FIELD_PARAMS)
        self.execution_semantics = self._normalize_execution_semantics(
            self.settings.get("execution_semantics", "snapshot")
        )
        self.current_mcs = 0
        self._script_cache = {}
        self._current_division_request = {}
        self._warned_fpp = False
        self._warned_cluster = False
        self._reported_fpp_success = False
        self._reported_visual_fpp_success = False
        self._reported_cluster_success = False
        self._reported_request_seen = False
        self._fpp_links_created = 0
        self._visual_fpp_links_created = 0
        self._rule_fpp_links_created = 0
        self._last_fpp_diag_mcs = -1
        self._warned_fpp_inventory = False
        self._cluster_tip_claim_mcs = None
        self._cluster_tip_claims = {}
        self._cluster_branch_claim_mcs = None
        self._cluster_branch_claims = {}
        self._internal_link_pairs = set()
        self._visual_link_pairs = set()
        self._last_hypha_summary_mcs = -1
        self._uses_death_status_field = True
        self._death_status_field_ready = False
        print("[GeneratedRuleEngine] loaded")


    def start(self):
        # === CC3D_VOLUME_HYPHAROOT START ===
        for cell in self.cell_list_by_type(self.HYPHAROOT):
            cell.targetVolume = 12.0
            cell.lambdaVolume = 18.0
        # === CC3D_VOLUME_HYPHAROOT END ===
        # === CC3D_VOLUME_INTERSTITIALSPACE START ===
        for cell in self.cell_list_by_type(self.INTERSTITIALSPACE):
            cell.targetVolume = 8.0
            cell.lambdaVolume = 10.0
        # === CC3D_VOLUME_INTERSTITIALSPACE END ===
        # === CC3D_VOLUME_DAMAGEDHOSTCELL START ===
        for cell in self.cell_list_by_type(self.DAMAGEDHOSTCELL):
            cell.targetVolume = 160.0
            cell.lambdaVolume = 1.5
        # === CC3D_VOLUME_DAMAGEDHOSTCELL END ===
        # === CC3D_VOLUME_HYPHASEGMENT START ===
        for cell in self.cell_list_by_type(self.HYPHASEGMENT):
            cell.targetVolume = 8.0
            cell.lambdaVolume = 8.0
        # === CC3D_VOLUME_HYPHASEGMENT END ===
        # === CC3D_VOLUME_HYPHATIP START ===
        for cell in self.cell_list_by_type(self.HYPHATIP):
            cell.targetVolume = 12.0
            cell.lambdaVolume = 8.0
        # === CC3D_VOLUME_HYPHATIP END ===
        # === CC3D_VOLUME_ATTACHEDFUNGUS START ===
        for cell in self.cell_list_by_type(self.ATTACHEDFUNGUS):
            cell.targetVolume = 18.0
            cell.lambdaVolume = 18.0
        # === CC3D_VOLUME_ATTACHEDFUNGUS END ===
        # === CC3D_VOLUME_FUNGUSYEAST START ===
        for cell in self.cell_list_by_type(self.FUNGUSYEAST):
            cell.targetVolume = 18.0
            cell.lambdaVolume = 8.0
        # === CC3D_VOLUME_FUNGUSYEAST END ===
        # === CC3D_VOLUME_HOSTCELL START ===
        for cell in self.cell_list_by_type(self.HOSTCELL):
            cell.targetVolume = 160.0
            cell.lambdaVolume = 1.5
        # === CC3D_VOLUME_HOSTCELL END ===
        self._ensure_death_status_field()
        self._apply_initial_celltype_constraints()
        self._prepare_cells()

    def _ensure_death_status_field(self):
        if not getattr(self, "_uses_death_status_field", False):
            return
        if getattr(self, "_death_status_field_ready", False):
            return
        try:
            self.create_scalar_field_cell_level_py("DeathStatus")
            self._death_status_field_ready = True
        except Exception as exc:
            print(f"[GeneratedRuleEngine] DeathStatus field unavailable: {exc}")

    def step(self, mcs):
        self.current_mcs = mcs
        self._prepare_cells()

        if self.execution_semantics == "asynchronous":
            self._step_asynchronous(mcs)
        else:
            self._step_snapshot(mcs)

        self._run_continuous_processes(mcs)

    def _prepare_cells(self):
        if self.cell_list is None:
            return
        for cell in self.cell_list:
            self._ensure_cell_dict(cell)

    def _apply_initial_celltype_constraints(self):
        if self.cell_list is None or not isinstance(self.celltype_params, dict):
            return

        applied = 0
        for type_name, params in self.celltype_params.items():
            if not isinstance(params, dict):
                continue

            type_id = self._cell_type_id(type_name)
            if type_id is None:
                continue

            for cell in self.cell_list_by_type(type_id):
                self._apply_celltype_constraints(cell, type_name)
                applied += 1

        if applied:
            print(f"[GeneratedRuleEngine] Applied celltype_params to {applied} initial cells.")

    def _ensure_cell_dict(self, cell):
        cell.dict.setdefault("state", {})
        cell.dict.setdefault("_internal", {})
        cell.dict["_internal"].setdefault("once_rules", {})
        cell.dict.setdefault("behaviour_stats", {})
        cell.dict.setdefault("persistent_tracking", {})

    def _step_snapshot(self, mcs):
        events = []
        seq = 0
        for original_index, rule in self._ordered_rules():
            new_events = self._events_for_rule(rule, original_index, mcs, seq)
            events.extend(new_events)
            seq += len(new_events)

        executed_once_rules = set()
        for event in sorted(events, key=lambda item: (item["order"], item["seq"])):
            if not self._execute_event(event, mcs):
                continue
            rule = event["rule"]
            if self._cell_once_rule(rule):
                self._mark_cell_once_triggered(event["cell"], rule)
            elif rule.get("once"):
                executed_once_rules.add(id(rule))

        for rule in self.rules:
            if id(rule) in executed_once_rules:
                rule["triggered"] = True

    def _step_asynchronous(self, mcs):
        seq = 0
        for original_index, rule in self._ordered_rules():
            events = self._events_for_rule(rule, original_index, mcs, seq)
            executed = False
            for event in events:
                event_executed = self._execute_event(event, mcs)
                if event_executed and self._cell_once_rule(rule):
                    self._mark_cell_once_triggered(event["cell"], rule)
                executed = event_executed or executed
            if executed and rule.get("once") and not self._cell_once_rule(rule):
                rule["triggered"] = True
            seq += len(events)

    def _ordered_rules(self):
        return list(enumerate(self.rules))

    def _rule_order(self, rule, original_index):
        # Generated CC3D code must mirror COMPILED_RULES top-to-bottom.
        # Ignore legacy rule["order"] values because CSV/template imports may
        # repeat or reset them across behaviour files.
        return float(original_index)

    def _events_for_rule(self, rule, original_index, mcs, seq_start):
        if self._global_once_triggered(rule):
            return []

        raw_freq = rule.get("frequency", 1)
        is_static_freq = not isinstance(raw_freq, dict)
        if is_static_freq and not self._frequency_matches(raw_freq, mcs):
            return []

        behaviour = rule.get("behaviour")
        order = self._rule_order(rule, original_index)

        if behaviour == "custom_script":
            if not is_static_freq and not self._frequency_matches(raw_freq, mcs, None):
                return []
            return [self._event(rule, None, None, order, seq_start, original_index)]

        if behaviour == "create":
            if not is_static_freq and not self._frequency_matches(raw_freq, mcs, None):
                return []
            return self._global_events_for_rule(rule, order, seq_start, original_index)

        target = rule.get("target")
        if not target:
            print(f"[GeneratedRuleEngine] Missing target for rule {rule.get('id')}")
            return []

        events = []
        for cell in self._target_cells(target):
            if cell.dict.get("is_dead", False):
                continue
            if cell.dict.get("dormant", False) and behaviour not in {"dormancy", "death"}:
                continue
            if self._cell_once_triggered(cell, rule):
                continue
            if not is_static_freq and not self._frequency_matches(raw_freq, mcs, cell):
                continue

            for case in rule.get("cases", []):
                if not self._evaluate_condition(case.get("when", {}), cell):
                    continue
                resolved_case = self._resolve_case(case, cell)
                events.append(self._event(rule, resolved_case, cell, order, seq_start + len(events), original_index))
                break
        return events

    def _global_events_for_rule(self, rule, order, seq_start, original_index):
        for case in rule.get("cases", []):
            if not self._evaluate_condition(case.get("when", {}), None):
                continue
            resolved_case = self._resolve_case(case, None)
            return [self._event(rule, resolved_case, None, order, seq_start, original_index)]
        return []

    def _event(self, rule, resolved_case, cell, order, seq, original_index):
        payload = self._case_payload(resolved_case) if isinstance(resolved_case, dict) else {}
        return {
            "rule": rule,
            "rule_id": rule.get("id"),
            "behaviour": rule.get("behaviour"),
            "case": resolved_case,
            "payload": payload,
            "cell": cell,
            "order": order,
            "seq": seq,
            "original_index": original_index,
        }

    def _cell_once_rule(self, rule):
        if not rule.get("once"):
            return False
        if rule.get("behaviour") in {"create", "custom_script"}:
            return False
        return bool(rule.get("target"))

    def _global_once_triggered(self, rule):
        return bool(rule.get("once") and not self._cell_once_rule(rule) and rule.get("triggered"))

    def _cell_once_key(self, rule):
        rule_id = rule.get("id")
        if rule_id is None or str(rule_id).strip() == "":
            return f"{rule.get('behaviour', 'rule')}:{id(rule)}"
        return str(rule_id)

    def _cell_once_triggered(self, cell, rule):
        if not self._cell_once_rule(rule) or cell is None:
            return False
        self._ensure_cell_dict(cell)
        once_rules = cell.dict["_internal"].setdefault("once_rules", {})
        return bool(once_rules.get(self._cell_once_key(rule), False))

    def _mark_cell_once_triggered(self, cell, rule):
        if not self._cell_once_rule(rule) or cell is None:
            return
        self._ensure_cell_dict(cell)
        once_rules = cell.dict["_internal"].setdefault("once_rules", {})
        once_rules[self._cell_once_key(rule)] = True

    def _execute_event(self, event, mcs):
        behaviour = event["behaviour"]
        cell = event["cell"]
        payload = dict(event["payload"])
        rule = event["rule"]

        if behaviour == "custom_script":
            return self._execute_custom_script(rule)

        if cell is not None:
            if cell.dict.get("is_dead", False) and behaviour != "death":
                return False
            if cell.dict.get("dormant", False) and behaviour not in {"dormancy", "death"}:
                return False

        payload["debug"] = bool(rule.get("debug") or payload.get("debug", False))
        hook_result = self._execute_user_hook(event, payload, mcs)
        if hook_result is not None:
            return hook_result

        handlers = {
            "growth": self._execute_growth,
            "differentiate": self._execute_differentiate,
            "create": self._execute_create,
            "death": self._execute_death,
            "secrete/uptake": self._execute_secrete_uptake,
            "dormancy": self._execute_dormancy,
            "phagocytosis": self._execute_phagocytosis,
            "chemotaxis": self._execute_chemotaxis,
            "force": self._execute_force,
            "compartmentalize": self._execute_compartmentalize,
            "fpp_link": self._execute_fpp_link,
        }
        handler = handlers.get(behaviour)
        if handler is None:
            print(f"[GeneratedRuleEngine] Unsupported behaviour: {behaviour}")
            return False

        return bool(handler(cell, payload, mcs))

    def _execute_user_hook(self, event, payload, mcs):
        rule = event["rule"]
        cell = event["cell"]
        hook_names = [
            self._hook_name("rule", rule.get("id")),
            self._hook_name("handle", event["behaviour"]),
        ]
        for hook_name in hook_names:
            hook = getattr(self, hook_name, None)
            if not callable(hook):
                continue
            try:
                result = self._call_user_hook(hook, cell, payload, mcs, rule, event)
            except Exception as exc:
                print(f"[GeneratedRuleEngine] User hook {hook_name} failed: {exc}")
                return False
            if result is NotImplemented or result == "default":
                return None
            if result is None:
                return True
            return bool(result)
        return None

    def _hook_name(self, prefix, raw_name):
        text = str(raw_name or "").strip()
        text = re.sub(r"\W", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        if not text:
            text = "unnamed"
        return f"{prefix}_{text}"

    def _call_user_hook(self, hook, cell, payload, mcs, rule, event):
        try:
            signature = inspect.signature(hook)
            positional = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind in (
                    parameter.POSITIONAL_ONLY,
                    parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            accepts_varargs = any(
                parameter.kind == parameter.VAR_POSITIONAL
                for parameter in signature.parameters.values()
            )
        except (TypeError, ValueError):
            positional = []
            accepts_varargs = True

        if accepts_varargs or len(positional) >= 5:
            return hook(cell, payload, mcs, rule, event)
        if len(positional) == 4:
            return hook(cell, payload, mcs, rule)
        return hook(cell, payload, mcs)

    def _case_payload(self, case):
        if not isinstance(case, dict):
            return {}
        return {key: value for key, value in case.items() if key != "when"}

    def _resolve_case(self, case, cell):
        payload = self._case_payload(copy.deepcopy(case))
        payload = self._resolve_dynamic_parameters(payload, cell)
        self._resolve_physical_model_values(payload, cell)
        return {"when": copy.deepcopy(case.get("when", {})), **payload}

    def _resolve_dynamic_parameters(self, data, cell):
        if cell is None:
            return data
        if isinstance(data, dict):
            resolved = {}
            local_vars = self._numeric_context(cell)
            local_vars.update({k: v for k, v in data.items() if isinstance(v, (int, float))})
            for key, value in data.items():
                if isinstance(value, str) and "{" in value and "}" in value:
                    try:
                        expr = value
                        for var_key, var_value in local_vars.items():
                            expr = expr.replace("{" + str(var_key) + "}", str(var_value))
                        import re
                        expr = re.sub(r"\{.*?}", "0", expr)
                        resolved[key] = float(eval(expr, {"__builtins__": None}, {"math": math, **local_vars}))
                    except Exception as exc:
                        print(f"[GeneratedRuleEngine] Dynamic parameter failed: {value}: {exc}")
                        resolved[key] = value
                else:
                    resolved[key] = self._resolve_dynamic_parameters(value, cell)
            return resolved
        if isinstance(data, list):
            return [self._resolve_dynamic_parameters(item, cell) for item in data]
        return data

    def _resolve_physical_model_values(self, target_dict, cell):
        if not isinstance(target_dict, dict):
            return
        for key, value in list(target_dict.items()):
            if isinstance(value, dict):
                if "model" in value and "parameters" in value:
                    target_dict[key] = self._solve_physical_model(value, cell)
                else:
                    self._resolve_physical_model_values(value, cell)
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict) and "model" in item and "parameters" in item:
                        value[idx] = self._solve_physical_model(item, cell)
                    else:
                        self._resolve_physical_model_values(item, cell)

    def _frequency_matches(self, raw_freq, mcs, cell=None):
        try:
            freq = self._solve_frequency(raw_freq, cell)
        except Exception:
            freq = 1
        return mcs % freq == 0

    def _solve_frequency(self, frequency_spec, cell):
        if not isinstance(frequency_spec, dict):
            return self._coerce_frequency(frequency_spec)
        if frequency_spec.get("type") == "state_feedback_frequency":
            return self._solve_state_feedback_frequency(frequency_spec, cell)
        return self._coerce_frequency(self._solve_physical_model(frequency_spec, cell))

    def _solve_state_feedback_frequency(self, spec, cell):
        state_key = spec.get("state_key", "division_count")
        state_val = self._frequency_state_value(cell, state_key)
        mode = spec.get("mode", "linear")
        try:
            if mode == "exponential":
                base = float(spec.get("base_frequency", 1.0))
                factor = float(spec.get("factor", 1.25))
                value = base * (factor ** state_val)
            elif mode == "expression":
                expr = spec.get("expression", "1")
                context = self._frequency_context(cell, state_key, state_val)
                value = float(eval(expr, {"__builtins__": None}, context))
            else:
                base = float(spec.get("base_frequency", 1.0))
                slope = float(spec.get("slope", 1.0))
                value = base + slope * state_val
        except Exception as exc:
            print(f"[GeneratedRuleEngine] Frequency feedback failed: {exc}")
            value = spec.get("min_frequency", 1.0)
        value = self._clamp_frequency(value, spec.get("min_frequency", 1.0), spec.get("max_frequency", 1000.0))
        return self._coerce_frequency(value)

    def _frequency_state_value(self, cell, state_key):
        state_key = str(state_key)
        if state_key == "mcs":
            return float(getattr(self, "current_mcs", 0))
        if cell is None:
            return 0.0
        context = self._numeric_context(cell)
        value = context.get(state_key)
        if value is None and state_key.startswith("cell."):
            value = context.get(state_key.split(".", 1)[1])
        if value is None:
            value = cell.dict.get(state_key)
        if value is None:
            value = self._flatten_cell_dict(cell.dict).get(state_key, 0.0)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _frequency_context(self, cell, state_key, state_val):
        context = {"math": math, "mcs": float(getattr(self, "current_mcs", 0)), "state": state_val, state_key: state_val}
        if cell is not None:
            context.update(self._numeric_context(cell))
            for key, value in self._flatten_cell_dict(cell.dict).items():
                if isinstance(value, (int, float, bool)):
                    context[key] = float(value)
        return context

    def _coerce_frequency(self, value):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 1.0
        if not math.isfinite(numeric) or numeric <= 0:
            numeric = 1.0
        return max(1, int(math.ceil(numeric)))

    def _clamp_frequency(self, value, min_frequency, max_frequency):
        try:
            min_val = float(min_frequency)
        except (TypeError, ValueError):
            min_val = 1.0
        try:
            max_val = float(max_frequency)
        except (TypeError, ValueError):
            max_val = 1000.0
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        return max(min_val, min(max_val, float(value)))

    def _normalize_execution_semantics(self, value):
        text = str(value or "snapshot").strip().lower()
        aliases = {
            "sync": "snapshot",
            "synchronous": "snapshot",
            "ordered": "snapshot",
            "async": "asynchronous",
            "legacy": "snapshot",
            "legacy_requests": "snapshot",
            "request_queue": "snapshot",
            "requests": "snapshot",
        }
        text = aliases.get(text, text)
        if text not in {"snapshot", "asynchronous"}:
            print(f"[GeneratedRuleEngine] Unknown execution_semantics={value!r}; using snapshot")
            return "snapshot"
        return text

    def _target_cells(self, target):
        target_text = str(target).strip()
        if target_text.lower() in {"global", "all", "*"}:
            return list(self.cell_list)
        return list(self.cell_list_by_type(getattr(self, target_text.upper(), 0)))

    def _evaluate_condition(self, block, cell):
        full_type = block.get("condition_type", block.get("type", "TRUE")) if isinstance(block, dict) else "TRUE"
        if str(full_type).startswith("Logic_"):
            logic = str(full_type).split("_", 1)[1].upper()
            conditions = block.get("params", {}).get("conditions", [])
            if logic == "AND":
                for cond in conditions:
                    if not self._evaluate_condition(cond, cell):
                        return False
                return True
            if logic == "OR":
                for cond in conditions:
                    if self._evaluate_condition(cond, cell):
                        return True
                return False
            if logic == "NOT":
                return not self._evaluate_condition(conditions[0], cell) if conditions else False
        return self._evaluate_single_condition(block, cell)

    def _evaluate_single_condition(self, cond, cell):
        if not isinstance(cond, dict):
            return True
        cond_type = cond.get("condition_type", cond.get("type", "TRUE"))
        params = cond.get("params", cond)
        cond_type_text = str(cond_type)

        if cond_type_text in {"TRUE", "True", "Always", "AlwaysTrue"}:
            return True
        if cond_type_text in {"TimeWindow", "time_window"}:
            start = self._condition_number(params.get("start", params.get("start_mcs", 0)), 0, cell)
            end = self._condition_number(params.get("end", params.get("end_mcs", float("inf"))), float("inf"), cell)
            return start <= self.current_mcs < end
        if cond_type_text in {"Probability", "probability"}:
            probability = self._condition_number(params.get("p", 0), 0, cell)
            return random.random() < max(0.0, min(1.0, probability))
        if cond_type_text == "Environment":
            if cell is None:
                return False
            field_name = str(params.get("field_name", "")).strip()
            operator = params.get("operator", ">")
            threshold = self._condition_number(params.get("threshold", params.get("value", 0.0)), 0.0, cell)
            value = self._environment_value(params, cell)
            return self._compare(value, operator, threshold)
        if cond_type_text in {"contact", "Contact"}:
            if cell is None:
                return False
            target_type = params.get("target_type")
            value = self._contact_ratio(cell, target_type)
            threshold = self._condition_number(params.get("threshold", 0.0), 0.0, cell)
            return self._compare(value, params.get("operator", ">"), threshold)
        if cond_type_text in {"duration", "Duration"}:
            if cell is None:
                return False
            threshold_mcs = self._condition_number(params.get("threshold_mcs", 0), 0, cell)
            sub_condition = params.get("sub_condition")
            if sub_condition is None:
                return False
            sub_ok = self._evaluate_condition(sub_condition, cell)
            key = json.dumps(sub_condition, sort_keys=True)
            internal = cell.dict.setdefault("_internal", {})
            if sub_ok:
                internal.setdefault(key, self.current_mcs)
                return (self.current_mcs - internal[key]) >= threshold_mcs
            internal.pop(key, None)
            return False
        if cond_type_text.startswith("Morphology"):
            if cell is None:
                return False
            indicator = cond_type_text.split("_", 1)[1] if "_" in cond_type_text else params.get("regulator", "volume")
            value = self._morphology_value(cell, indicator)
            threshold = self._condition_number(params.get("threshold", params.get("value", 0.0)), 0.0, cell)
            return self._compare(value, params.get("operator", ">"), threshold)
        if cond_type_text in {"state", "State"}:
            if cell is None:
                return False
            regulator = str(params.get("regulator", "")).strip()
            threshold = params.get("threshold", params.get("value", 0.0))
            if regulator == "dormant":
                expected = str(threshold).strip().lower() in {"true", "1", "yes", "y"}
                return bool(cell.dict.get("dormant", False)) == expected
            value = self._frequency_state_value(cell, regulator)
            return self._compare(value, params.get("operator", "=="), self._condition_number(threshold, 0.0, cell))
        if cond_type_text == "Custom":
            return self._evaluate_custom_condition(cond, cell, params)
        return False

    def _evaluate_custom_condition(self, cond, cell, params):
        script_path = cond.get("script_path") or params.get("script_path")
        if not script_path:
            return False
        path = self._resolve_script_path(script_path)
        if not path.exists():
            print(f"[GeneratedRuleEngine] Custom condition script not found: {path}")
            return False
        try:
            spec = importlib.util.spec_from_file_location("generated_custom_condition", path)
            if spec is None or spec.loader is None:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "validate"):
                return bool(module.validate(cell, self, params))
            if hasattr(module, "evaluate"):
                return bool(module.evaluate(cell, self, params))
        except Exception as exc:
            print(f"[GeneratedRuleEngine] Custom condition failed: {exc}")
        return False

    def _resolve_script_path(self, script_path):
        path = Path(str(script_path)).expanduser()
        if path.is_absolute():
            return path
        candidates = [
            GENERATED_CODE_DIR / path,
            Path.cwd() / path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _compare(self, value, operator, threshold):
        try:
            left = float(value)
            right = float(threshold)
        except (TypeError, ValueError):
            left = value
            right = threshold
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
        return False

    def _execute_growth(self, cell, payload, mcs):
        delta = self._solve_growth_model(payload, cell)
        cell.targetVolume += delta
        self._record_active_step(cell, "growth", mcs, delta)
        if payload.get("debug"):
            print(f"[GeneratedGrowth] mcs={mcs} cell={cell.id} delta={delta} targetVolume={cell.targetVolume}")
        return True

    def _execute_differentiate(self, cell, payload, mcs):
        mode = payload.get("mode")
        if mode == "type_switch":
            new_type = payload.get("new_type")
            if not new_type:
                return False
            old_type = self.get_type_name_by_cell(cell)
            cell.type = getattr(self, str(new_type).upper())
            self._apply_celltype_constraints(cell, new_type)
            self._record_event(cell, "type_switch", mcs)
            self._set_metric(cell, "type_switch", "from_type", old_type)
            self._set_metric(cell, "type_switch", "to_type", new_type)
            return True
        if mode == "division":
            cell.dict.setdefault("_internal", {})["division_in_progress"] = True
            cell.dict["_internal"]["division_request"] = payload
            cell.dict["_division_request"] = payload
            self._current_division_request = payload
            placement = payload.get("placement", {"type": "random"})
            placement_type = placement.get("type", "random")
            if placement_type == "angle":
                theta = math.radians(self._to_float(placement.get("angle_deg", 0), 0))
                self.divide_cell_orientation_vector_based(cell, math.cos(theta), math.sin(theta), 0)
            elif placement_type == "vector":
                self.divide_cell_orientation_vector_based(
                    cell,
                    self._to_float(placement.get("dx", 1), 1),
                    self._to_float(placement.get("dy", 0), 0),
                    self._to_float(placement.get("dz", 0), 0),
                )
            else:
                self.divide_cell_random_orientation(cell)
            return True
        print(f"[GeneratedDifferentiate] Unknown mode: {mode}")
        return False

    def _execute_create(self, _cell, payload, mcs):
        cell_type = payload.get("cell_type")
        count = max(0, int(self._to_float(payload.get("count", 1), 1)))
        if not cell_type or count <= 0:
            return False
        type_id = self._cell_type_id(cell_type)
        if type_id is None:
            print(f"[GeneratedCreate] Unknown cell type: {cell_type}")
            return False
        dist = payload.get("distribution", {"type": "random"})
        dist_type = dist.get("type", "random")
        created = 0
        if dist_type == "cluster":
            created = self._create_cluster(type_id, cell_type, count, dist, mcs)
        elif dist_type == "stripe":
            created = self._create_stripe(type_id, cell_type, count, dist, mcs)
        else:
            created = self._create_random(type_id, cell_type, count, dist, mcs)
        if payload.get("debug"):
            print(f"[GeneratedCreate] mcs={mcs} type={cell_type} requested={count} created={created}")
        return created > 0

    def _execute_death(self, cell, payload, mcs):
        mode = payload.get("mode")
        if mode not in {"apoptosis", "necrosis"}:
            print(f"[GeneratedDeath] Unknown mode: {mode}")
            return False
        if cell.dict.get("is_dead"):
            return False
        cell.dict["is_dead"] = True
        cell.dict["death_params"] = dict(payload)
        if mode == "apoptosis":
            cell.dict["death_state"] = "apoptosis"
            self._set_death_status(cell, 1.0)
        else:
            cell.dict["death_state"] = "necrosis_swelling"
            self._set_death_status(cell, 2.0)
        self._record_event(cell, "death", mcs)
        self._record_activation(cell, "death", mcs)
        self._set_metric(cell, "death", "mode", mode)
        self._set_metric(cell, "death", "state", cell.dict["death_state"])
        self._clear_non_death_state(cell)
        return True

    def _execute_secrete_uptake(self, cell, payload, mcs):
        field_name = payload.get("field_name")
        secret_mode = payload.get("secret_mode")
        if not field_name or not secret_mode:
            return False
        secretor = self.get_field_secretor(field_name)
        if not secretor:
            print(f"[GeneratedSecretion] Secretor for field {field_name!r} not found")
            return False
        method_name = secret_mode
        if payload.get("total_count") and not method_name.endswith("TotalCount"):
            method_name += "TotalCount"
        method = getattr(secretor, method_name, None)
        if method is None:
            print(f"[GeneratedSecretion] Secretor method not found: {method_name}")
            return False
        amount = self._to_float(payload.get("amount", 1.0), 1.0)
        relative_uptake = self._to_float(payload.get("relative_uptake", 0.1), 0.1)
        contact_type_ids = self._contact_type_ids(payload.get("contact_types", []))
        try:
            if "uptake" in secret_mode:
                result = method(cell, amount, relative_uptake, contact_type_ids) if "OnContactWith" in secret_mode else method(cell, amount, relative_uptake)
            else:
                result = method(cell, amount, contact_type_ids) if "OnContactWith" in secret_mode else method(cell, amount)
            actual_amount = getattr(result, "tot_amount", amount)
            actual_delta = abs(actual_amount)
            self._record_active_step(cell, "secrete_uptake", mcs, actual_delta)
            self._record_field_delta(cell, "secrete_uptake", field_name, mcs, actual_delta)
            self._set_metric(cell, "secrete_uptake", "last_field", field_name)
            self._set_metric(cell, "secrete_uptake", "last_mode", secret_mode)
            if payload.get("total_count") and result:
                tracking = cell.dict.setdefault("persistent_tracking", {})
                tracking[field_name] = tracking.get(field_name, 0.0) + abs(result.tot_amount)
            return True
        except Exception as exc:
            print(f"[GeneratedSecretion] Failed: {exc}")
            return False

    def _execute_dormancy(self, cell, payload, mcs):
        action = payload.get("action", payload.get("mode", "dormant"))
        if action == "dormant":
            if not cell.dict.get("dormant", False):
                cell.dict["dormant"] = True
                self._record_event(cell, "dormancy", mcs)
            self._record_active_step(cell, "dormancy", mcs)
            self._set_metric(cell, "dormancy", "last_action", "dormant")
            return True
        if action == "reactivate":
            if cell.dict.get("dormant", False):
                cell.dict["dormant"] = False
                self._record_event(cell, "dormancy", mcs)
                self._record_deactivation(cell, "dormancy", mcs)
            self._set_metric(cell, "dormancy", "last_action", "reactivate")
            return True
        print(f"[GeneratedDormancy] Unknown action: {action}")
        return False

    def _execute_phagocytosis(self, cell, payload, mcs):
        mode = payload.get("phago_mode", "engulfment")
        eating_rate = self._to_float(payload.get("eating_rate", 2.0), 2.0)
        leak_field = payload.get("leak_field", "None")
        leak_amount = self._to_float(payload.get("leak_amount", 0.0), 0.0)
        if mode == "frustrated":
            acted = False
            for neighbor, _area in self.getCellNeighborDataList(cell):
                if not neighbor:
                    continue
                if neighbor.type == cell.type:
                    mover = getattr(self, "move_cell_pixels", None)
                    if mover:
                        mover(neighbor, cell)
                        acted = True
                if self._should_leak(leak_field, leak_amount):
                    self._leak_inside_cell(cell, leak_field, leak_amount * 2.0)
                    acted = True
                if acted:
                    self._record_active_step(cell, "phagocytosis", mcs)
                    self._set_metric(cell, "phagocytosis", "mode", "frustrated")
            return acted
        target_type_id = self._cell_type_id(payload.get("target_cell_type"))
        if target_type_id is None:
            print(f"[GeneratedPhagocytosis] Unknown target type: {payload.get('target_cell_type')}")
            return False
        acted = False
        for neighbor, _area in self.getCellNeighborDataList(cell):
            if not neighbor or neighbor.type != target_type_id:
                continue
            actual_eat = min(eating_rate, neighbor.volume)
            if actual_eat <= 0:
                continue
            neighbor.targetVolume = max(0.0, neighbor.targetVolume - actual_eat)
            cell.targetVolume += actual_eat
            self._record_active_step(cell, "phagocytosis", mcs, actual_eat)
            self._set_metric(cell, "phagocytosis", "mode", mode)
            self._set_metric(cell, "phagocytosis", "last_target_type_id", target_type_id)
            if mode == "absorption":
                self._leak_inside_cell(cell, leak_field, leak_amount)
            else:
                self._leak_at_com(cell, leak_field, leak_amount)
            if neighbor.volume <= 1:
                cell.dict["phago_count"] = cell.dict.get("phago_count", 0) + 1
                self._sync_event_count(cell, "phagocytosis", mcs, cell.dict["phago_count"])
            acted = True
            if mode == "engulfment":
                break
        return acted

    def _execute_chemotaxis(self, cell, payload, mcs):
        plugin = getattr(self, "chemotaxisPlugin", None)
        if not plugin:
            return False
        field_name = payload.get("field_name", "ATTR")
        strategy = payload.get("target_strategy", "break")
        is_target = False
        if strategy == "break":
            is_target = True
        elif strategy == "id" and cell.id == payload.get("target_cell_id"):
            is_target = True
        elif strategy in {"coord", "coordinate"}:
            tx = self._to_float(payload.get("target_x", 0), 0)
            ty = self._to_float(payload.get("target_y", 0), 0)
            if math.sqrt((cell.xCOM - tx) ** 2 + (cell.yCOM - ty) ** 2) <= 3.0:
                is_target = True
        if not is_target:
            return False
        data = plugin.getChemotaxisData(cell, field_name)
        if not data:
            data = plugin.addChemotaxisData(cell, field_name)
        actual_lambda = self._to_float(payload.get("lambda", 20.0), 20.0)
        data.setLambda(actual_lambda)
        formula_name = payload.get("formula", "Standard")
        if formula_name != "Standard":
            data.setChemotaxisFormulaByName(formula_name)
            coef = payload.get("coef")
            if coef is not None:
                if formula_name == "Saturation":
                    data.setSaturationCoef(float(coef))
                elif formula_name == "SaturationLinear":
                    data.setSaturationLinearCoef(float(coef))
                elif formula_name == "LogScaled":
                    data.setLogScaledCoef(float(coef))
        self._record_active_step(cell, "chemotaxis", mcs)
        self._set_metric(cell, "chemotaxis", "field_name", field_name)
        self._set_metric(cell, "chemotaxis", "lambda", actual_lambda)
        self._set_metric(cell, "chemotaxis", "formula", formula_name)
        return True

    def _execute_force(self, cell, payload, mcs):
        mode = str(payload.get("mode", "vector")).strip().lower()
        if mode == "clear":
            self._clear_force(cell, mcs)
            cell.dict.pop("active_force", None)
            return True
        direction = self._force_direction(cell, payload, mode)
        if direction is None:
            if payload.get("debug"):
                print(f"[GeneratedForce] No valid direction for cell {cell.id}, mode={mode}")
            return False
        force = self._to_float(payload.get("force", payload.get("magnitude", 1.0)), 1.0)
        decay = self._to_float(payload.get("decay", 1.0), 1.0)
        if decay != 1.0 and cell.dict.get("active_force"):
            force *= decay
            payload["force"] = force
        cell.lambdaVecX = -force * direction[0]
        cell.lambdaVecY = -force * direction[1]
        cell.lambdaVecZ = -force * direction[2]
        cell.dict["_force_executed_mcs"] = mcs
        if payload.get("persist"):
            cell.dict["active_force"] = dict(payload)
        else:
            cell.dict.pop("active_force", None)
        self._record_active_step(cell, "force", mcs, abs(force))
        self._set_metric(cell, "force", "mode", mode)
        self._set_metric(cell, "force", "force", force)
        self._set_metric(cell, "force", "dir_x", direction[0])
        self._set_metric(cell, "force", "dir_y", direction[1])
        self._set_metric(cell, "force", "dir_z", direction[2])
        return True

    def _execute_fpp_link(self, cell, payload, mcs):
        mode = str(payload.get("mode", "nearest_type")).strip().lower()
        if mode in {"clear", "remove_all"}:
            try:
                self.remove_all_cell_fpp_links(cell, links=True)
                self._record_event(cell, "fpp_link", mcs, 0)
                self._set_metric(cell, "fpp_link", "last_created", 0)
                self._set_metric(cell, "fpp_link", "mode", "clear")
                return True
            except Exception as exc:
                if payload.get("debug"):
                    print(f"[GeneratedFPPLink] Failed to clear FPP links for cell={cell.id}: {exc}")
                return False

        partners = self._fpp_link_partners(cell, payload, mode)
        if not partners:
            if payload.get("debug"):
                print(f"[GeneratedFPPLink] No partner found for cell={cell.id} mode={mode}")
            return False

        created = 0
        for partner in partners:
            if partner is None or partner.id == cell.id:
                continue
            if self._fpp_link_exists(cell, partner):
                continue
            if self._create_ordinary_fpp_link(cell, partner, payload):
                created += 1

        if created:
            self._record_event(cell, "fpp_link", mcs, created)
            self._set_metric(cell, "fpp_link", "last_created", created)
            self._set_metric(cell, "fpp_link", "total_created", self._rule_fpp_links_created)
            self._set_metric(cell, "fpp_link", "mode", mode)
            if payload.get("debug"):
                print(
                    f"[GeneratedFPPLink] created={created} total={self._rule_fpp_links_created} "
                    f"cell={cell.id} mode={mode}"
                )
            return True
        return False

    def _execute_compartmentalize(self, cell, payload, mcs):
        action = str(payload.get("action", "extend_chain")).strip().lower()
        self._maybe_report_compartment_runtime_state(cell, payload, mcs)
        self._maybe_report_hypha_summary(mcs)
        if not self._reported_request_seen:
            print(
                "[GeneratedCompartmentalize] first request received: "
                f"mcs={mcs} cell={cell.id if cell is not None else None} action={action}"
            )
            self._reported_request_seen = True
        if action in {"initialize", "initialize_cluster", "init_cluster"}:
            self._mark_as_compartment(cell, payload, mcs, is_tip=True)
            cell.dict.setdefault("hypha_length", 1)
            cell.dict.setdefault("branch_count", 0)
            self._record_event(cell, "compartmentalize", mcs)
            self._set_metric(cell, "compartmentalize", "action", "initialize_cluster")
            return True
        if action in {"extend", "extend_chain"}:
            return self._extend_compartment_chain(cell, payload, mcs)
        if action in {"branch", "branch_chain"}:
            return self._branch_compartment_chain(cell, payload, mcs)
        print(f"[GeneratedCompartmentalize] Unknown action: {action}")
        return False

    def _run_continuous_processes(self, mcs):
        if self.cell_list is None:
            return
        for cell in list(self.cell_list):
            if cell.dict.get("is_dead"):
                self._advance_death(cell, mcs)
                self._clear_force(cell, mcs=None)
                cell.dict.pop("active_force", None)
                continue
            active_force = cell.dict.get("active_force")
            if active_force and cell.dict.get("_force_executed_mcs") != mcs:
                self._execute_force(cell, dict(active_force), mcs)
            if cell.dict.get("dormant"):
                self._record_active_step(cell, "dormancy", mcs)

    def _advance_death(self, cell, mcs):
        state = cell.dict.get("death_state")
        if not state:
            self._set_death_status(cell, 0.0)
            return
        self._record_active_step(cell, "death", mcs)
        self._set_metric(cell, "death", "state", state)
        params = cell.dict.get("death_params", {})
        if state == "apoptosis":
            shrink_rate = self._to_float(params.get("shrink_rate", 0.95), 0.95)
            terminal_volume = self._to_float(params.get("terminal_volume", 0.0), 0.0)
            cell.targetVolume *= shrink_rate
            if cell.targetVolume <= max(terminal_volume, 1.0):
                if self._as_bool(params.get("delete_on_terminal", False)):
                    self.delete_cell(cell)
                    return
                cell.targetVolume = terminal_volume
                cell.lambdaVolume = 100.0
        elif state == "necrosis_swelling":
            swell_rate = self._to_float(params.get("swell_rate", 1.05), 1.05)
            max_volume = self._to_float(params.get("max_target_volume", 150.0), 150.0)
            cell.targetVolume *= swell_rate
            if cell.targetVolume >= max_volume:
                for field_info in params.get("fields", []):
                    self._release_field(cell, field_info)
                cell.dict["death_state"] = "necrosis_shrinking"
                self._set_death_status(cell, 3.0)
        elif state == "necrosis_shrinking":
            post_shrink = self._to_float(params.get("post_burst_shrink_rate", 0.8), 0.8)
            cell.targetVolume *= post_shrink
            if cell.targetVolume < 1.0:
                if self._as_bool(params.get("delete_on_terminal", False)):
                    self.delete_cell(cell)
                    return
                cell.targetVolume = 0.0
                cell.lambdaVolume = 100.0

    def _solve_growth_model(self, payload, cell):
        model = payload.get("model", "linear")
        if model == "hill":
            regulators = payload.get("regulator")
            if not regulators:
                return 0.0
            if not isinstance(regulators, list):
                regulators = [regulators]
            y_max = self._to_float(payload.get("y_max", 1.0), 1.0)
            y_min = self._to_float(payload.get("y_min", 0.0), 0.0)
            k_val = self._to_float(payload.get("K", payload.get("k", 0.5)), 0.5)
            n_val = self._to_float(payload.get("n", 2.0), 2.0)
            product = 1.0
            for regulator in regulators:
                value = self._field_value(regulator, cell)
                product *= (value ** n_val) / (k_val ** n_val + value ** n_val + 1e-12)
            return float(y_min + (y_max - y_min) * product)
        if model == "expression":
            expr = payload.get("expression")
            if not expr:
                return 0.0
            context = self._numeric_context(cell)
            for field_name in dir(self.field):
                if field_name.startswith("_"):
                    continue
                try:
                    field = getattr(self.field, field_name)
                    context[field_name] = float(field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)])
                except Exception:
                    pass
            try:
                return float(eval(expr, {"__builtins__": None}, {"math": math, "min": min, "max": max, "abs": abs, **context}))
            except Exception as exc:
                print(f"[GeneratedGrowth] Expression failed: {expr}: {exc}")
                return 0.0
        regulators = payload.get("regulator")
        alpha = payload.get("alpha", 1.0)
        if not regulators:
            return 0.0
        regulators = regulators if isinstance(regulators, list) else [regulators]
        alphas = alpha if isinstance(alpha, list) else [alpha] * len(regulators)
        return sum(self._to_float(coef, 0.0) * self._field_value(reg, cell) for reg, coef in zip(regulators, alphas))

    def _solve_physical_model(self, model_dict, cell):
        if not isinstance(model_dict, dict) or "model" not in model_dict:
            return model_dict
        model_type = model_dict.get("model")
        params = model_dict.get("parameters", {})
        merged = {"model": model_type, "regulator": model_dict.get("regulator"), **params}
        return self._solve_growth_model(merged, cell)

    def _create_random(self, type_id, cell_type, count, dist, mcs):
        x_start = int(self._to_float(dist.get("x_start", 0), 0))
        x_end = int(self._to_float(dist.get("x_end", self.dim.x), self.dim.x))
        y_start = int(self._to_float(dist.get("y_start", 0), 0))
        y_end = int(self._to_float(dist.get("y_end", self.dim.y), self.dim.y))
        created = 0
        attempts = 0
        while created < count and attempts < count * 20:
            x = random.randint(x_start, max(x_start, x_end - 1))
            y = random.randint(y_start, max(y_start, y_end - 1))
            if self.cell_field[x, y, 0] is None:
                self._place_new_cell(type_id, cell_type, x, y, 0, mcs)
                created += 1
            attempts += 1
        return created

    def _create_cluster(self, type_id, cell_type, count, dist, mcs):
        center = dist.get("center", [self.dim.x // 2, self.dim.y // 2])
        cx, cy = center[0], center[1]
        radius = self._to_float(dist.get("radius", 20), 20)
        created = 0
        attempts = 0
        while created < count and attempts < count * 20:
            angle = random.uniform(0, 2.0 * math.pi)
            distance = random.uniform(0, radius)
            x = int(cx + distance * math.cos(angle))
            y = int(cy + distance * math.sin(angle))
            if 0 <= x < self.dim.x and 0 <= y < self.dim.y and self.cell_field[x, y, 0] is None:
                self._place_new_cell(type_id, cell_type, x, y, 0, mcs)
                created += 1
            attempts += 1
        return created

    def _create_stripe(self, type_id, cell_type, count, dist, mcs):
        direction = dist.get("direction", "vertical")
        coords = []
        if direction == "vertical":
            x = int(self._to_float(dist.get("x", 0), 0))
            y_start = int(self._to_float(dist.get("y_start", 0), 0))
            if "y_gap" in dist:
                coords = [(x, y_start + i * int(self._to_float(dist.get("y_gap"), 1))) for i in range(count)]
            else:
                y_end = self._to_float(dist.get("y_end", self.dim.y), self.dim.y)
                step = (y_end - y_start) / (count - 1) if count > 1 else 0
                coords = [(x, int(y_start + i * step)) for i in range(count)]
        else:
            y = int(self._to_float(dist.get("y", 0), 0))
            x_start = int(self._to_float(dist.get("x_start", 0), 0))
            if "x_gap" in dist:
                coords = [(x_start + i * int(self._to_float(dist.get("x_gap"), 1)), y) for i in range(count)]
            else:
                x_end = self._to_float(dist.get("x_end", self.dim.x), self.dim.x)
                step = (x_end - x_start) / (count - 1) if count > 1 else 0
                coords = [(int(x_start + i * step), y) for i in range(count)]
        created = 0
        for x, y in coords:
            if 0 <= x < self.dim.x and 0 <= y < self.dim.y and self.cell_field[x, y, 0] is None:
                self._place_new_cell(type_id, cell_type, x, y, 0, mcs)
                created += 1
        return created

    def _place_new_cell(self, type_id, cell_type, x, y, z, mcs):
        cell = self.new_cell(type_id)
        self._apply_celltype_constraints(cell, cell_type)
        self.cell_field[x, y, z] = cell
        cell.dict["created_mcs"] = mcs
        self._record_event(cell, "create", mcs)
        self._set_metric(cell, "create", "cell_type", cell_type)
        return cell

    def _extend_compartment_chain(self, tip_cell, payload, mcs, direction_override=None):
        interval = max(1, int(self._to_float(payload.get("extension_interval", 1), 1)))
        if not tip_cell.dict.get("compartment_enabled"):
            self._mark_as_compartment(tip_cell, payload, mcs, is_tip=True)
            tip_cell.dict.setdefault("hypha_length", 1)
            tip_cell.dict.setdefault("branch_count", 0)
            tip_cell.dict["tip_seed_mcs"] = mcs
            if self._as_bool(payload.get("delay_first_extension", False)):
                delay = max(0, int(self._to_float(payload.get("initial_extension_delay", interval), interval)))
                tip_cell.dict["last_extension_mcs"] = mcs - max(0, interval - delay)
                return False

        last_mcs = tip_cell.dict.get("last_extension_mcs")
        if last_mcs is not None and (mcs - last_mcs) < interval:
            return False
        max_length = self._to_float(payload.get("max_length", 0), 0)
        current_length = self._to_float(tip_cell.dict.get("hypha_length", 1), 1)
        if max_length > 0 and current_length >= max_length:
            return False
        current_branch_length = self._to_float(tip_cell.dict.get("branch_length", current_length), current_length)
        max_branch_length = self._to_float(payload.get("max_branch_length", 0), 0)
        if (
            max_branch_length > 0
            and current_branch_length >= max_branch_length
            and self._branch_length_limit_applies(tip_cell, payload)
        ):
            return False
        segment_type_id = self._cell_type_id(payload.get("segment_type") or payload.get("cell_type"))
        tip_type_id = self._cell_type_id(payload.get("tip_type") or payload.get("segment_type") or payload.get("cell_type"))
        if segment_type_id is None or tip_type_id is None:
            print("[GeneratedCompartmentalize] Missing or unknown segment/tip type")
            return False
        if (
            direction_override is None
            and self._cluster_tip_selection_enabled(payload)
            and not self._claim_cluster_tip_extension(
                tip_cell,
                payload,
                mcs,
                interval,
                max_length,
                max_branch_length,
                tip_type_id,
            )
        ):
            return False
        direction = direction_override or self._compartment_direction(tip_cell, payload)
        if direction is None:
            return False
        direction = self._apply_direction_noise(direction, payload)
        site = self._front_extension_site(
            tip_cell,
            direction,
            max(1.0, self._to_float(payload.get("step_length", 1.0), 1.0)),
            int(self._to_float(payload.get("search_radius", 3), 3)),
            payload,
        )
        if site is None:
            return False
        cluster_id = tip_cell.clusterId
        previous_tip_id = tip_cell.id
        previous_parent_id = tip_cell.dict.get("parent_segment_id")
        previous_parent = self._cell_by_id(previous_parent_id)
        root_type_id = self._cell_type_id(payload.get("root_type", "HyphaRoot"))
        previous_parent_is_root = (
            previous_parent is not None
            and root_type_id is not None
            and getattr(previous_parent, "type", None) == root_type_id
        )
        first_tip_from_root = bool(tip_cell.dict.get("compartment_is_first_tip_from_root", False)) or previous_parent_is_root
        tip_cell.type = segment_type_id
        self._apply_celltype_constraints(tip_cell, payload.get("segment_type"))
        tip_cell.dict["is_hypha_tip"] = False
        tip_cell.dict["is_compartment_tip"] = False
        tip_cell.dict["is_root_child_segment"] = first_tip_from_root
        tip_cell.dict["last_extension_mcs"] = mcs
        new_tip = self.new_cell(tip_type_id)
        self._copy_cell_constraints(tip_cell, new_tip)
        self._apply_celltype_constraints(new_tip, payload.get("tip_type"))
        replaced_cell = self.cell_field[site[0], site[1], site[2]]
        if replaced_cell is not None:
            new_tip.dict["replaced_cell_id"] = replaced_cell.id
            new_tip.dict["replaced_cell_type"] = self.get_type_name_by_cell(replaced_cell)
        self.cell_field[site[0], site[1], site[2]] = new_tip
        new_tip.dict["seed_pixels"] = self._seed_tip_patch(new_tip, site, payload)
        new_tip.dict["bridge_pixels"] = self._bridge_parent_to_tip(tip_cell, new_tip, site, payload)
        self._reassign_cluster(new_tip, cluster_id, payload)
        self._mark_as_compartment(new_tip, payload, mcs, is_tip=True)
        new_tip.dict["parent_segment_id"] = previous_tip_id
        new_tip.dict["hypha_length"] = current_length + 1
        if self._as_bool(payload.get("start_new_branch", False)):
            new_tip.dict["branch_length"] = 1
            new_tip.dict["branch_root_id"] = previous_tip_id
            new_tip.dict["branch_id"] = new_tip.id
            new_tip.dict["branch_is_lateral"] = True
        else:
            new_tip.dict["branch_length"] = current_branch_length + 1
            new_tip.dict["branch_root_id"] = tip_cell.dict.get("branch_root_id", previous_tip_id)
            new_tip.dict["branch_id"] = tip_cell.dict.get("branch_id", previous_tip_id)
            new_tip.dict["branch_is_lateral"] = bool(tip_cell.dict.get("branch_is_lateral", False))
        new_tip.dict["last_extension_mcs"] = mcs
        new_tip.dict["orientation_x"] = direction[0]
        new_tip.dict["orientation_y"] = direction[1]
        new_tip.dict["orientation_z"] = direction[2]
        if self._as_bool(payload.get("use_fpp_link", False)):
            self._link_internal(tip_cell, new_tip, payload)
        if self._as_bool(payload.get("visualize_fpp_link", False)):
            self._link_visual(tip_cell, new_tip, payload)
        self._record_event(new_tip, "compartmentalize", mcs)
        self._set_metric(new_tip, "compartmentalize", "action", "extend_chain")
        self._set_metric(new_tip, "compartmentalize", "length", current_length + 1)
        self._set_metric(new_tip, "compartmentalize", "parent_segment_id", previous_tip_id)
        return True

    def _branch_compartment_chain(self, segment_cell, payload, mcs):
        max_branches = int(self._to_float(
            payload.get("max_branches_per_segment", payload.get("max_branch_tips_per_segment", 1)),
            1,
        ))
        current_branches = int(self._to_float(segment_cell.dict.get("branch_count", 0), 0))
        if max_branches > 0 and current_branches >= max_branches:
            return False

        branch_interval = max(1, int(self._to_float(
            payload.get("branch_interval", payload.get("extension_interval", 1)),
            1,
        )))
        last_branch_mcs = segment_cell.dict.get("last_branch_mcs")
        if last_branch_mcs is not None and (mcs - last_branch_mcs) < branch_interval:
            return False

        if not self._branch_source_allowed(segment_cell, payload):
            return False

        max_branch_length = self._to_float(payload.get("max_branch_length", 0), 0)
        if max_branch_length > 0 and max_branch_length <= 1:
            return False

        segment_type_id = self._cell_type_id(payload.get("segment_type") or payload.get("cell_type"))
        tip_type_id = self._cell_type_id(payload.get("tip_type") or payload.get("segment_type") or payload.get("cell_type"))
        if segment_type_id is None or tip_type_id is None:
            print("[GeneratedCompartmentalize] Missing or unknown segment/tip type for branch")
            return False

        cluster_id = getattr(segment_cell, "clusterId", None)
        if not self._claim_cluster_branch_event(cluster_id, payload, mcs, segment_cell, segment_type_id, branch_interval):
            return False

        probability = self._to_float(payload.get("branch_probability", 1.0), 1.0)
        if random.random() > max(0.0, min(1.0, probability)):
            return False

        max_active_tips = int(self._to_float(payload.get("max_active_tips_per_cluster", 0), 0))
        max_length = self._to_float(payload.get("max_length", 0), 0)
        if (
            max_active_tips > 0
            and self._active_tip_count(cluster_id, tip_type_id, max_length, max_branch_length) >= max_active_tips
        ):
            return False

        base_direction = self._compartment_direction(segment_cell, payload) or (1.0, 0.0, 0.0)
        branch_direction = self._branch_direction(base_direction, payload) or base_direction
        site = self._front_extension_site(
            segment_cell,
            branch_direction,
            max(1.0, self._to_float(payload.get("branch_step_length", payload.get("step_length", 1.0)), 1.0)),
            int(self._to_float(payload.get("branch_search_radius", payload.get("search_radius", 3)), 3)),
            payload,
        )
        if site is None:
            return False

        cluster_id = segment_cell.clusterId
        new_tip = self.new_cell(tip_type_id)
        self._copy_cell_constraints(segment_cell, new_tip)
        self._apply_celltype_constraints(new_tip, payload.get("tip_type"))
        replaced_cell = self.cell_field[site[0], site[1], site[2]]
        if replaced_cell is not None:
            new_tip.dict["replaced_cell_id"] = replaced_cell.id
            new_tip.dict["replaced_cell_type"] = self.get_type_name_by_cell(replaced_cell)
        self.cell_field[site[0], site[1], site[2]] = new_tip
        new_tip.dict["seed_pixels"] = self._seed_tip_patch(new_tip, site, payload)
        new_tip.dict["bridge_pixels"] = self._bridge_parent_to_tip(segment_cell, new_tip, site, payload)
        self._reassign_cluster(new_tip, cluster_id, payload)
        self._mark_as_compartment(new_tip, payload, mcs, is_tip=True)
        new_tip.dict["parent_segment_id"] = segment_cell.id
        new_tip.dict["branch_root_id"] = segment_cell.id
        new_tip.dict["branch_length"] = 1
        new_tip.dict["branch_id"] = new_tip.id
        new_tip.dict["branch_is_lateral"] = True
        new_tip.dict["hypha_length"] = self._to_float(segment_cell.dict.get("hypha_length", 1), 1) + 1
        new_tip.dict["last_extension_mcs"] = mcs
        new_tip.dict["orientation_x"] = branch_direction[0]
        new_tip.dict["orientation_y"] = branch_direction[1]
        new_tip.dict["orientation_z"] = branch_direction[2]

        segment_cell.dict["branch_count"] = current_branches + 1
        segment_cell.dict["last_branch_mcs"] = mcs

        if self._as_bool(payload.get("use_fpp_link", False)):
            self._link_internal(segment_cell, new_tip, payload)
        if self._as_bool(payload.get("visualize_fpp_link", False)):
            self._link_visual(segment_cell, new_tip, payload)

        self._record_event(new_tip, "compartmentalize", mcs)
        self._set_metric(new_tip, "compartmentalize", "action", "branch_chain")
        self._set_metric(new_tip, "compartmentalize", "parent_segment_id", segment_cell.id)
        self._set_metric(new_tip, "compartmentalize", "branch_length", 1)
        self._set_metric(segment_cell, "compartmentalize", "branch_count", segment_cell.dict["branch_count"])
        return True

    def _cluster_tip_selection_enabled(self, payload):
        mode = str(
            payload.get("cluster_tip_selection", payload.get("tip_selection", ""))
        ).strip().lower()
        return (
            mode in {"random_one_per_cluster", "one_per_cluster", "random"}
            or self._as_bool(payload.get("single_tip_per_cluster", False))
        )

    def _claim_cluster_tip_extension(
        self,
        tip_cell,
        payload,
        mcs,
        interval,
        max_length,
        max_branch_length,
        tip_type_id,
    ):
        cluster_id = getattr(tip_cell, "clusterId", None)
        if cluster_id is None:
            return True

        if self._cluster_tip_claim_mcs != mcs:
            self._cluster_tip_claims = {}
            self._cluster_tip_claim_mcs = mcs

        group = str(payload.get("tip_selection_group", "extend_chain"))
        key = (cluster_id, group)
        if key not in self._cluster_tip_claims:
            candidates = self._eligible_tip_ids(
                cluster_id,
                tip_type_id,
                mcs,
                interval,
                max_length,
                max_branch_length,
            )
            if not candidates:
                return False
            self._cluster_tip_claims[key] = random.choice(candidates)

        return self._cluster_tip_claims.get(key) == tip_cell.id

    def _eligible_tip_ids(self, cluster_id, tip_type_id, mcs, interval, max_length, max_branch_length):
        candidates = []
        if self.cell_list is None:
            return candidates
        for candidate in list(self.cell_list):
            if getattr(candidate, "clusterId", None) != cluster_id:
                continue
            if getattr(candidate, "type", None) != tip_type_id:
                continue
            if candidate.dict.get("is_dead") or not candidate.dict.get("is_hypha_tip"):
                continue
            last_mcs = candidate.dict.get("last_extension_mcs")
            if last_mcs is not None and (mcs - last_mcs) < interval:
                continue
            current_length = self._to_float(candidate.dict.get("hypha_length", 1), 1)
            if max_length > 0 and current_length >= max_length:
                continue
            current_branch_length = self._to_float(candidate.dict.get("branch_length", current_length), current_length)
            if max_branch_length > 0 and current_branch_length >= max_branch_length:
                continue
            candidates.append(candidate.id)
        return candidates

    def _claim_cluster_branch_event(self, cluster_id, payload, mcs, segment_cell=None, segment_type_id=None, branch_interval=1):
        if cluster_id is None:
            return True
        if not self._as_bool(payload.get("single_branch_per_cluster", True)):
            return True
        if self._cluster_branch_claim_mcs != mcs:
            self._cluster_branch_claims = {}
            self._cluster_branch_claim_mcs = mcs
        group = str(payload.get("branch_selection_group", "branch_chain"))
        key = (cluster_id, group)
        if key not in self._cluster_branch_claims:
            candidates = self._eligible_branch_segment_ids(
                cluster_id,
                segment_type_id,
                payload,
                mcs,
                branch_interval,
            )
            if not candidates and segment_cell is not None:
                candidates = [segment_cell.id]
            if not candidates:
                return False
            self._cluster_branch_claims[key] = random.choice(candidates)
        return segment_cell is not None and self._cluster_branch_claims.get(key) == segment_cell.id

    def _eligible_branch_segment_ids(self, cluster_id, segment_type_id, payload, mcs, branch_interval):
        candidates = []
        if self.cell_list is None:
            return candidates
        max_branches = int(self._to_float(
            payload.get("max_branches_per_segment", payload.get("max_branch_tips_per_segment", 1)),
            1,
        ))
        for candidate in list(self.cell_list):
            if getattr(candidate, "clusterId", None) != cluster_id:
                continue
            if segment_type_id is not None and getattr(candidate, "type", None) != segment_type_id:
                continue
            if candidate.dict.get("is_dead"):
                continue
            if not self._branch_source_allowed(candidate, payload):
                continue
            current_branches = int(self._to_float(candidate.dict.get("branch_count", 0), 0))
            if max_branches > 0 and current_branches >= max_branches:
                continue
            last_branch_mcs = candidate.dict.get("last_branch_mcs")
            if last_branch_mcs is not None and (mcs - last_branch_mcs) < branch_interval:
                continue
            if (
                self._as_bool(payload.get("compartment_single_extend_per_branch", False))
                and not bool(candidate.dict.get("compartment_can_extend", False))
            ):
                continue
            candidates.append(candidate.id)
        return candidates

    def _branch_source_allowed(self, segment_cell, payload):
        mode = str(
            payload.get("branch_source_filter", payload.get("branch_source", ""))
        ).strip().lower()
        root_adjacent_only = (
            mode in {"root_child", "root_adjacent", "segment1", "first_segment"}
            or self._as_bool(payload.get("root_adjacent_only", False))
            or self._as_bool(payload.get("branch_from_root_child_only", False))
        )
        if not root_adjacent_only:
            return True
        if bool(segment_cell.dict.get("is_root_child_segment", False)):
            return True
        parent = self._cell_by_id(segment_cell.dict.get("parent_segment_id"))
        root_type_id = self._cell_type_id(payload.get("root_type", "HyphaRoot"))
        return parent is not None and root_type_id is not None and getattr(parent, "type", None) == root_type_id

    def _branch_length_limit_applies(self, tip_cell, payload):
        if self._as_bool(payload.get("limit_primary_branch_length", False)):
            return True
        return bool(tip_cell.dict.get("branch_is_lateral", False))

    def _active_tip_count(self, cluster_id, tip_type_id, max_length=0, max_branch_length=0):
        if cluster_id is None or self.cell_list is None:
            return 0
        active = 0
        for candidate in self.cell_list:
            if getattr(candidate, "clusterId", None) != cluster_id:
                continue
            if getattr(candidate, "type", None) != tip_type_id:
                continue
            if candidate.dict.get("is_dead") or not candidate.dict.get("is_hypha_tip"):
                continue
            current_length = self._to_float(candidate.dict.get("hypha_length", 1), 1)
            if max_length > 0 and current_length >= max_length:
                continue
            current_branch_length = self._to_float(candidate.dict.get("branch_length", current_length), current_length)
            if max_branch_length > 0 and current_branch_length >= max_branch_length:
                continue
            active += 1
        return active

    def _mark_as_compartment(self, cell, payload, mcs, is_tip):
        cell.dict["compartment_enabled"] = True
        cell.dict["compartment_cluster_id"] = getattr(cell, "clusterId", None)
        cell.dict["compartment_action_mcs"] = mcs
        cell.dict["is_compartment_tip"] = bool(is_tip)
        cell.dict["is_hypha_tip"] = bool(is_tip)
        cell.dict.setdefault("orientation_x", self._to_float(payload.get("dx", 1.0), 1.0))
        cell.dict.setdefault("orientation_y", self._to_float(payload.get("dy", 0.0), 0.0))
        cell.dict.setdefault("orientation_z", self._to_float(payload.get("dz", 0.0), 0.0))

    def _compartment_direction(self, cell, payload):
        mode = str(payload.get("direction_mode", payload.get("mode", "stored_vector"))).strip().lower()
        if mode in {"stored_vector", "inherit_orientation"}:
            return self._normalize((
                self._dict_number(cell, "orientation_x", self._to_float(payload.get("dx", 1.0), 1.0)),
                self._dict_number(cell, "orientation_y", self._to_float(payload.get("dy", 0.0), 0.0)),
                self._dict_number(cell, "orientation_z", self._to_float(payload.get("dz", 0.0), 0.0)),
            ))
        if mode == "vector":
            return self._normalize((
                self._to_float(payload.get("dx", 1.0), 1.0),
                self._to_float(payload.get("dy", 0.0), 0.0),
                self._to_float(payload.get("dz", 0.0), 0.0),
            ))
        if mode == "random_persistent":
            direction = self._normalize((
                self._dict_number(cell, "orientation_x", 0.0),
                self._dict_number(cell, "orientation_y", 0.0),
                self._dict_number(cell, "orientation_z", 0.0),
            ))
            if direction is None:
                angle = random.random() * 2.0 * math.pi
                direction = (math.cos(angle), math.sin(angle), 0.0)
                cell.dict["orientation_x"] = direction[0]
                cell.dict["orientation_y"] = direction[1]
                cell.dict["orientation_z"] = direction[2]
            return direction
        if mode == "toward_position":
            return self._normalize((
                self._to_float(payload.get("target_x", payload.get("x", cell.xCOM)), cell.xCOM) - cell.xCOM,
                self._to_float(payload.get("target_y", payload.get("y", cell.yCOM)), cell.yCOM) - cell.yCOM,
                self._to_float(payload.get("target_z", payload.get("z", cell.zCOM)), cell.zCOM) - cell.zCOM,
            ))
        if mode in {"toward_nearest_type", "toward_nearest_tissue", "into_tissue"}:
            target = self._nearest_cell_by_types(cell, payload.get("direction_target_types") or payload.get("direction_target_type") or payload.get("target_cell_type"))
            if target is not None:
                return self._normalize((target.xCOM - cell.xCOM, target.yCOM - cell.yCOM, target.zCOM - cell.zCOM))
            return self._normalize((
                self._to_float(payload.get("dx", 1.0), 1.0),
                self._to_float(payload.get("dy", 0.0), 0.0),
                self._to_float(payload.get("dz", 0.0), 0.0),
            ))
        if mode == "toward_field_gradient":
            return self._field_gradient_direction(cell, payload)
        if mode == "inherit_force_vector":
            return self._normalize((-cell.lambdaVecX, -cell.lambdaVecY, -cell.lambdaVecZ))
        return None

    def _force_direction(self, cell, payload, mode):
        if mode == "vector":
            return self._normalize((
                self._to_float(payload.get("dx", payload.get("x", 0.0)), 0.0),
                self._to_float(payload.get("dy", payload.get("y", 0.0)), 0.0),
                self._to_float(payload.get("dz", payload.get("z", 0.0)), 0.0),
            ))
        if mode == "stored_vector":
            prefix = str(payload.get("vector_prefix", "orientation")).strip() or "orientation"
            return self._normalize((
                self._dict_number(cell, f"{prefix}_x", 1.0),
                self._dict_number(cell, f"{prefix}_y", 0.0),
                self._dict_number(cell, f"{prefix}_z", 0.0),
            ))
        if mode in {"toward_position", "away_from_position"}:
            target = (
                self._to_float(payload.get("target_x", payload.get("x", cell.xCOM)), cell.xCOM),
                self._to_float(payload.get("target_y", payload.get("y", cell.yCOM)), cell.yCOM),
                self._to_float(payload.get("target_z", payload.get("z", cell.zCOM)), cell.zCOM),
            )
            vector = (target[0] - cell.xCOM, target[1] - cell.yCOM, target[2] - cell.zCOM)
            if mode == "away_from_position":
                vector = (-vector[0], -vector[1], -vector[2])
            return self._normalize(vector)
        if mode == "toward_cell_id":
            target = self._cell_by_id(payload.get("target_cell_id"))
            if target is None:
                return None
            return self._normalize((target.xCOM - cell.xCOM, target.yCOM - cell.yCOM, target.zCOM - cell.zCOM))
        if mode in {"toward_nearest_type", "away_from_nearest_type"}:
            target = self._nearest_cell_by_type(cell, payload.get("target_type") or payload.get("cell_type") or payload.get("target_cell_type"))
            if target is None:
                return None
            vector = (target.xCOM - cell.xCOM, target.yCOM - cell.yCOM, target.zCOM - cell.zCOM)
            if mode == "away_from_nearest_type":
                vector = (-vector[0], -vector[1], -vector[2])
            return self._normalize(vector)
        if mode == "toward_field_gradient":
            return self._field_gradient_direction(cell, payload)
        return None

    def _front_empty_site(self, cell, direction, step_length, search_radius, payload=None):
        return self._front_extension_site(cell, direction, step_length, search_radius, payload)

    def _front_extension_site(self, cell, direction, step_length, search_radius, payload=None):
        payload = payload or {}
        target = (
            self._clamp_index(cell.xCOM + direction[0] * step_length, self.dim.x),
            self._clamp_index(cell.yCOM + direction[1] * step_length, self.dim.y),
            self._clamp_index(cell.zCOM + direction[2] * step_length, self.dim.z),
        )
        mode = str(payload.get("site_selection_mode", "empty_first")).strip().lower()
        if mode in {"directional_replace_first", "directional_occupied_first", "line_replace_first"}:
            site = self._find_directional_replace_site(cell, direction, step_length, search_radius, payload)
            if site is not None:
                return site
            if self._as_bool(payload.get("require_replace_site", False)):
                return None
            return self._find_empty_site(target, search_radius)
        if mode in {"occupied_first", "replace_first", "host_first"}:
            site = self._find_replace_site(target, search_radius, payload)
            if site is not None:
                return site
            return self._find_empty_site(target, search_radius)
        if mode in {"front_occupied_first", "front_replace_first"}:
            site = self._find_replace_site(target, 0, payload)
            if site is not None:
                return site
            site = self._find_empty_site(target, search_radius)
            return site if site is not None else self._find_replace_site(target, search_radius, payload)
        site = self._find_empty_site(target, search_radius)
        return site if site is not None else self._find_replace_site(target, search_radius, payload)

    def _find_empty_site(self, target, search_radius):
        if self.cell_field[target[0], target[1], target[2]] is None:
            return target
        z_iter = [0] if self.dim.z <= 1 else None
        for radius in range(1, max(1, search_radius) + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    dz_values = z_iter if z_iter is not None else range(-radius, radius + 1)
                    for dz in dz_values:
                        x = self._clamp_index(target[0] + dx, self.dim.x)
                        y = self._clamp_index(target[1] + dy, self.dim.y)
                        z = self._clamp_index(target[2] + dz, self.dim.z)
                        if self.cell_field[x, y, z] is None:
                            return (x, y, z)
        return None

    def _find_replace_site(self, target, search_radius, payload):
        replace_type_ids = self._replace_target_type_ids(payload or {})
        if replace_type_ids:
            z_iter = [0] if self.dim.z <= 1 else None
            for radius in range(0, max(1, search_radius) + 1):
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        dz_values = z_iter if z_iter is not None else range(-radius, radius + 1)
                        for dz in dz_values:
                            x = self._clamp_index(target[0] + dx, self.dim.x)
                            y = self._clamp_index(target[1] + dy, self.dim.y)
                            z = self._clamp_index(target[2] + dz, self.dim.z)
                            occupant = self.cell_field[x, y, z]
                            if occupant is not None and occupant.type in replace_type_ids:
                                return (x, y, z)
        return None

    def _find_directional_replace_site(self, cell, direction, step_length, search_radius, payload):
        replace_type_ids = self._replace_target_type_ids(payload or {})
        if not replace_type_ids:
            return None

        best_site = None
        best_score = None
        target = (
            self._clamp_index(cell.xCOM + direction[0] * step_length, self.dim.x),
            self._clamp_index(cell.yCOM + direction[1] * step_length, self.dim.y),
            self._clamp_index(cell.zCOM + direction[2] * step_length, self.dim.z),
        )

        z_iter = [0] if self.dim.z <= 1 else None
        for radius in range(0, max(1, search_radius) + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    dz_values = z_iter if z_iter is not None else range(-radius, radius + 1)
                    for dz in dz_values:
                        x = self._clamp_index(target[0] + dx, self.dim.x)
                        y = self._clamp_index(target[1] + dy, self.dim.y)
                        z = self._clamp_index(target[2] + dz, self.dim.z)
                        occupant = self.cell_field[x, y, z]
                        if occupant is None or occupant.type not in replace_type_ids:
                            continue

                        vx = x - cell.xCOM
                        vy = y - cell.yCOM
                        vz = z - cell.zCOM
                        projection = vx * direction[0] + vy * direction[1] + vz * direction[2]
                        if projection <= 0:
                            continue

                        total_sq = vx * vx + vy * vy + vz * vz
                        perp_sq = max(0.0, total_sq - projection * projection)
                        axial_error = abs(projection - step_length)
                        score = (perp_sq, axial_error, total_sq)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_site = (x, y, z)

        return best_site

    def _seed_tip_patch(self, cell, site, payload):
        radius = max(0, int(self._to_float(payload.get("tip_seed_radius", payload.get("seed_radius", 1)), 1)))
        if radius <= 0:
            return 1
        replace_type_ids = self._replace_target_type_ids(payload or {})
        seeded = 0
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                dz_values = [0] if self.dim.z <= 1 else range(-radius, radius + 1)
                for dz in dz_values:
                    if self.dim.z > 1 and dx * dx + dy * dy + dz * dz > radius * radius:
                        continue
                    x = self._clamp_index(site[0] + dx, self.dim.x)
                    y = self._clamp_index(site[1] + dy, self.dim.y)
                    z = self._clamp_index(site[2] + dz, self.dim.z)
                    occupant = self.cell_field[x, y, z]
                    if occupant is None or occupant is cell or occupant.type in replace_type_ids:
                        self.cell_field[x, y, z] = cell
                        seeded += 1
        return max(1, seeded)

    def _bridge_parent_to_tip(self, parent_cell, child_cell, site, payload):
        if not self._as_bool(payload.get("bridge_to_tip", True)):
            return 0
        replace_type_ids = self._replace_target_type_ids(payload or {})
        start = (float(parent_cell.xCOM), float(parent_cell.yCOM), float(parent_cell.zCOM))
        end = (float(site[0]), float(site[1]), float(site[2]))
        steps = int(max(abs(end[0] - start[0]), abs(end[1] - start[1]), abs(end[2] - start[2])))
        if steps <= 1:
            return 0
        bridged = 0
        for index in range(1, steps):
            fraction = index / float(steps)
            x = self._clamp_index(start[0] + (end[0] - start[0]) * fraction, self.dim.x)
            y = self._clamp_index(start[1] + (end[1] - start[1]) * fraction, self.dim.y)
            z = self._clamp_index(start[2] + (end[2] - start[2]) * fraction, self.dim.z)
            occupant = self.cell_field[x, y, z]
            if (
                occupant is None
                or occupant is parent_cell
                or occupant is child_cell
                or occupant.type in replace_type_ids
            ):
                self.cell_field[x, y, z] = parent_cell
                bridged += 1
        return bridged

    def _apply_direction_noise(self, direction, payload):
        noise = self._to_float(payload.get("direction_noise", payload.get("angle_noise", 0.0)), 0.0)
        if noise <= 0.0:
            return direction
        angle = math.atan2(direction[1], direction[0])
        angle += random.uniform(-noise, noise)
        noisy = self._normalize((math.cos(angle), math.sin(angle), direction[2]))
        return noisy or direction

    def _branch_direction(self, base_direction, payload):
        base = self._normalize(base_direction)
        if base is None:
            return None
        mode = str(payload.get("branch_direction_mode", "angle")).strip().lower()
        if mode in {"random", "random_persistent"}:
            angle = random.random() * 2.0 * math.pi
            return self._normalize((math.cos(angle), math.sin(angle), base[2]))
        min_angle = payload.get("branch_angle_min_degrees", payload.get("branch_min_angle_degrees"))
        max_angle = payload.get("branch_angle_max_degrees", payload.get("branch_max_angle_degrees"))
        if min_angle is not None or max_angle is not None:
            low = self._to_float(min_angle, 30.0)
            high = self._to_float(max_angle, 60.0)
            if high < low:
                low, high = high, low
            angle_degrees = random.uniform(low, high)
        else:
            angle_degrees = self._to_float(
                payload.get("branch_angle_degrees", payload.get("branch_angle", 45.0)),
                45.0,
            )
            jitter_degrees = self._to_float(
                payload.get("branch_angle_jitter_degrees", payload.get("branch_angle_jitter", 0.0)),
                0.0,
            )
            angle_degrees += random.uniform(-jitter_degrees, jitter_degrees)
        sign = -1.0 if random.random() < 0.5 else 1.0
        angle = math.atan2(base[1], base[0])
        branch_angle = math.radians(angle_degrees)
        angle += sign * branch_angle
        return self._normalize((math.cos(angle), math.sin(angle), base[2]))

    def _replace_target_type_ids(self, payload):
        if not self._as_bool(payload.get("allow_occupied_site", payload.get("allow_replace", False))):
            return set()
        raw_types = (
            payload.get("replace_target_types")
            or payload.get("replace_types")
            or payload.get("target_types")
            or payload.get("target_type")
            or []
        )
        if isinstance(raw_types, str):
            raw_types = [part.strip() for part in raw_types.split(",") if part.strip()]
        type_ids = set()
        for type_name in raw_types:
            type_id = self._cell_type_id(type_name)
            if type_id is not None:
                type_ids.add(type_id)
        return type_ids

    def _field_gradient_direction(self, cell, payload):
        field_name = payload.get("field_name") or payload.get("field")
        if not field_name:
            return None
        try:
            field = getattr(self.field, str(field_name))
        except Exception:
            return None
        step = max(1, int(self._to_float(payload.get("gradient_step", payload.get("step", 1)), 1)))
        x = self._clamp_index(cell.xCOM, self.dim.x)
        y = self._clamp_index(cell.yCOM, self.dim.y)
        z = self._clamp_index(cell.zCOM, self.dim.z)
        x0, x1 = max(0, x - step), min(self.dim.x - 1, x + step)
        y0, y1 = max(0, y - step), min(self.dim.y - 1, y + step)
        z0, z1 = max(0, z - step), min(self.dim.z - 1, z + step)
        try:
            gx = float(field[x1, y, z]) - float(field[x0, y, z])
            gy = float(field[x, y1, z]) - float(field[x, y0, z])
            gz = 0.0 if self.dim.z <= 1 else float(field[x, y, z1]) - float(field[x, y, z0])
        except Exception:
            return None
        return self._normalize((gx, gy, gz))

    def _numeric_context(self, cell):
        specs = {
            "cell_id": "id",
            "cell_type": "type",
            "type_id": "type",
            "volume": "volume",
            "surface": "surface",
            "targetVolume": "targetVolume",
            "targetvolume": "targetVolume",
            "lambdaVolume": "lambdaVolume",
            "lambdavolume": "lambdaVolume",
            "targetSurface": "targetSurface",
            "targetsurface": "targetSurface",
            "lambdaSurface": "lambdaSurface",
            "lambdasurface": "lambdaSurface",
            "xCOM": "xCOM",
            "yCOM": "yCOM",
            "zCOM": "zCOM",
            "xCM": "xCM",
            "yCM": "yCM",
            "zCM": "zCM",
            "eccentricity": "eccentricity",
            "ecc": "ecc",
            "cluster_id": "clusterId",
            "lambdaVecX": "lambdaVecX",
            "lambdaVecY": "lambdaVecY",
            "lambdaVecZ": "lambdaVecZ",
        }
        context = {}
        for key, attr in specs.items():
            value = self._numeric_attr(cell, attr)
            if value is not None:
                context[key] = value
                context[f"cell.{key}"] = value
        return context

    def _numeric_attr(self, obj, attr_name):
        try:
            value = getattr(obj, attr_name)
        except Exception:
            return None
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
        return None

    def _morphology_value(self, cell, indicator):
        indicator = str(indicator).lower()
        if indicator in {"elongation", "aspect_ratio"}:
            ecc = self._numeric_attr(cell, "eccentricity")
            if ecc is None:
                ecc = self._numeric_attr(cell, "ecc") or 0.0
            if ecc < 0.0001:
                return 1.0
            if ecc > 0.999:
                return 30.0
            return 1.0 / math.sqrt(1.0 - ecc ** 2)
        if indicator in {"specific_surface", "specificsurface"}:
            volume = self._numeric_attr(cell, "volume") or 0.0
            surface = self._numeric_attr(cell, "surface") or 0.0
            return 0.0 if volume == 0 else surface / volume
        return self._numeric_attr(cell, indicator) or 0.0

    def _condition_number(self, value, default=0.0, cell=None):
        if value in (None, ""):
            return float(default)
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            if "model" in value and "parameters" in value:
                try:
                    return float(self._solve_physical_model(value, cell))
                except Exception as exc:
                    print(f"[GeneratedRuleEngine] Condition physical model failed: {exc}")
            return float(default)

        text = str(value).strip()
        if text.lower() in {"inf", "+inf", "infinity", "+infinity"}:
            return float("inf")
        try:
            return float(text)
        except ValueError:
            pass

        expr = text
        for key in re.findall(r"\{([^{}]+)\}", text):
            expr = expr.replace(f"{{{key}}}", str(self._frequency_state_value(cell, key)))

        try:
            context = self._frequency_context(cell, "state", 0.0)
            return float(eval(expr, {"__builtins__": None}, context))
        except Exception as exc:
            print(f"[GeneratedRuleEngine] Condition numeric evaluation failed for {value!r}: {exc}")
            return float(default)

    def _environment_value(self, params, cell):
        field_name = str(params.get("field_name", "")).strip()
        if not field_name or cell is None:
            return 0.0
        try:
            field = getattr(self.field, field_name)
        except Exception:
            return 0.0

        mode = self._environment_sampling_mode(params.get("sampling_mode", params.get("environment_mode", "com")))
        if mode == "com":
            return self._sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM)

        if mode.startswith("radius_"):
            radius = max(0, int(round(self._condition_number(params.get("radius", params.get("sampling_radius", 1)), 1, cell))))
            return self._aggregate_samples(self._radius_field_samples(field, cell, radius), mode.split("_", 1)[1])

        if mode.startswith("contact_boundary_"):
            target_type = params.get("target_type") or params.get("contact_target_type") or params.get("sampling_target_type")
            target_type_id = self._cell_type_id(target_type)
            if target_type_id is None or self._contact_ratio(cell, target_type) <= 0:
                return 0.0
            pixels = self._cell_pixels(cell)
            if not pixels:
                return self._sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM)
            samples = [
                self._sample_field_at(field, x, y, z)
                for x, y, z in pixels
                if self._has_neighbor_type(x, y, z, target_type_id)
            ]
            return self._aggregate_samples(samples, mode.rsplit("_", 1)[1])

        pixels = self._cell_pixels(cell)
        if not pixels:
            return self._sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM)

        if mode.startswith("cell_"):
            samples = [self._sample_field_at(field, x, y, z) for x, y, z in pixels]
            return self._aggregate_samples(samples, mode.split("_", 1)[1])

        if mode.startswith("boundary_"):
            samples = [
                self._sample_field_at(field, x, y, z)
                for x, y, z in pixels
                if self._is_boundary_pixel(cell, x, y, z)
            ]
            return self._aggregate_samples(samples, mode.split("_", 1)[1])

        return self._sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM)

    def _environment_sampling_mode(self, raw_mode):
        aliases = {
            "": "com",
            "center": "com",
            "centre": "com",
            "cell_center": "com",
            "cell_com": "com",
            "com": "com",
            "cell": "cell_average",
            "cell_avg": "cell_average",
            "cell_average": "cell_average",
            "cell_mean": "cell_average",
            "cell_max": "cell_max",
            "cell_min": "cell_min",
            "boundary": "boundary_average",
            "boundary_avg": "boundary_average",
            "boundary_average": "boundary_average",
            "boundary_mean": "boundary_average",
            "boundary_max": "boundary_max",
            "boundary_min": "boundary_min",
            "contact_boundary": "contact_boundary_average",
            "contact_boundary_avg": "contact_boundary_average",
            "contact_boundary_average": "contact_boundary_average",
            "contact_boundary_mean": "contact_boundary_average",
            "contact_boundary_max": "contact_boundary_max",
            "contact_boundary_min": "contact_boundary_min",
            "radius": "radius_average",
            "radius_avg": "radius_average",
            "radius_average": "radius_average",
            "radius_mean": "radius_average",
            "radius_max": "radius_max",
            "radius_min": "radius_min",
        }
        return aliases.get(str(raw_mode or "com").strip().lower(), "com")

    def _sample_field_at(self, field, x, y, z):
        xi = self._clamp_index(x, self.dim.x)
        yi = self._clamp_index(y, self.dim.y)
        zi = self._clamp_index(z, self.dim.z)
        try:
            return float(field[xi, yi, zi])
        except Exception:
            return 0.0

    def _radius_field_samples(self, field, cell, radius):
        cx = self._clamp_index(cell.xCOM, self.dim.x)
        cy = self._clamp_index(cell.yCOM, self.dim.y)
        cz = self._clamp_index(cell.zCOM, self.dim.z)
        radius_sq = radius * radius
        z_values = [cz] if self.dim.z <= 1 else range(max(0, cz - radius), min(self.dim.z - 1, cz + radius) + 1)
        samples = []
        for x in range(max(0, cx - radius), min(self.dim.x - 1, cx + radius) + 1):
            for y in range(max(0, cy - radius), min(self.dim.y - 1, cy + radius) + 1):
                for z in z_values:
                    if (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 <= radius_sq:
                        samples.append(self._sample_field_at(field, x, y, z))
        return samples

    def _aggregate_samples(self, samples, method):
        if not samples:
            return 0.0
        if method == "max":
            return max(samples)
        if method == "min":
            return min(samples)
        return sum(samples) / len(samples)

    def _cell_pixels(self, cell):
        for method_name in ("get_cell_pixel_list", "getCellPixelList"):
            method = getattr(self, method_name, None)
            if method is None:
                continue
            try:
                pixels = []
                for item in method(cell):
                    coords = self._pixel_coords(item)
                    if coords is not None:
                        pixels.append(coords)
                return pixels
            except Exception:
                continue
        return []

    def _pixel_coords(self, item):
        pixel = getattr(item, "pixel", item)
        try:
            return int(pixel.x), int(pixel.y), int(pixel.z)
        except Exception:
            try:
                return int(pixel[0]), int(pixel[1]), int(pixel[2] if len(pixel) > 2 else 0)
            except Exception:
                return None

    def _is_boundary_pixel(self, cell, x, y, z):
        for nx, ny, nz in self._neighbor_sites(x, y, z):
            try:
                neighbor = self.cell_field[nx, ny, nz]
            except Exception:
                return True
            if neighbor is None or getattr(neighbor, "id", None) != getattr(cell, "id", None):
                return True
        return False

    def _has_neighbor_type(self, x, y, z, target_type_id):
        for nx, ny, nz in self._neighbor_sites(x, y, z):
            try:
                neighbor = self.cell_field[nx, ny, nz]
            except Exception:
                continue
            if neighbor is not None and getattr(neighbor, "type", None) == target_type_id:
                return True
        return False

    def _neighbor_sites(self, x, y, z):
        offsets = [(-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0)]
        if self.dim.z > 1:
            offsets.extend([(0, 0, -1), (0, 0, 1)])
        for dx, dy, dz in offsets:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < self.dim.x and 0 <= ny < self.dim.y and 0 <= nz < self.dim.z:
                yield nx, ny, nz

    def _field_value(self, field_name, cell):
        if not field_name or cell is None:
            return 0.0
        try:
            field = getattr(self.field, str(field_name))
            return self._sample_field_at(field, cell.xCOM, cell.yCOM, cell.zCOM)
        except Exception:
            return 0.0

    def _contact_ratio(self, cell, target_type_name):
        target_type_id = self._cell_type_id(target_type_name)
        if target_type_id is None:
            return 0.0
        target_area = 0.0
        total_area = 0.0
        for neighbor, area in self.getCellNeighborDataList(cell):
            total_area += area
            if neighbor and neighbor.type == target_type_id:
                target_area += area
        return target_area / total_area if total_area > 0 else 0.0

    def _cell_type_id(self, type_name):
        if not type_name:
            return None
        return getattr(self, str(type_name).strip().upper(), None)

    def _contact_type_ids(self, contact_types):
        if isinstance(contact_types, str):
            contact_types = [part.strip() for part in contact_types.split(",") if part.strip()]
        return [self._cell_type_id(name) for name in contact_types if self._cell_type_id(name) is not None]

    def _apply_celltype_constraints(self, cell, type_name):
        params = self.celltype_params.get(str(type_name), {}) if type_name else {}
        for key, attr in (
            ("targetVolume", "targetVolume"),
            ("lambdaVolume", "lambdaVolume"),
            ("targetSurface", "targetSurface"),
            ("lambdaSurface", "lambdaSurface"),
            ("fluctAmpl", "fluctAmpl"),
        ):
            if key in params:
                try:
                    setattr(cell, attr, params[key])
                except Exception:
                    pass

    def _copy_cell_constraints(self, source, target):
        for attr in ("targetVolume", "lambdaVolume", "targetSurface", "lambdaSurface", "fluctAmpl"):
            try:
                setattr(target, attr, getattr(source, attr))
            except Exception:
                pass

    def _reassign_cluster(self, cell, cluster_id, payload):
        try:
            self.reassign_cluster_id(cell=cell, cluster_id=cluster_id)
            if not self._reported_cluster_success:
                print(
                    "[GeneratedCompartmentalize] cluster reassignment active: "
                    f"cell={cell.id} cluster={cell.clusterId}"
                )
                self._reported_cluster_success = True
        except Exception as exc:
            if payload.get("debug") or not self._warned_cluster:
                print(f"[GeneratedCompartmentalize] Could not reassign cluster: {exc}")
                self._warned_cluster = True

    def _link_internal(self, cell_a, cell_b, payload):
        pair_key = self._link_pair_key(cell_a, cell_b)
        if pair_key in self._internal_link_pairs:
            return
        try:
            if self._internal_link_exists(cell_a, cell_b):
                self._internal_link_pairs.add(pair_key)
                return
            link = self.new_fpp_internal_link(
                cell_a,
                cell_b,
                self._to_float(payload.get("link_lambda", payload.get("lambda_distance", 10.0)), 10.0),
                self._to_float(payload.get("target_distance", 0.0), 0.0),
                self._to_float(payload.get("max_distance", 0.0), 0.0),
            )
            if link is None and not self._warned_fpp:
                print("[GeneratedCompartmentalize] FPP plugin is not loaded; internal link skipped")
                self._warned_fpp = True
            elif link is not None:
                self._internal_link_pairs.add(pair_key)
                self._fpp_links_created += 1
                if not self._reported_fpp_success:
                    print(
                        "[GeneratedCompartmentalize] FPP internal link active: "
                        f"created={self._fpp_links_created} "
                        f"cell_a={cell_a.id} cell_b={cell_b.id}"
                    )
                    self._reported_fpp_success = True
        except Exception as exc:
            if payload.get("debug") or not self._warned_fpp:
                print(f"[GeneratedCompartmentalize] FPP link failed: {exc}")
                self._warned_fpp = True

    def _internal_link_exists(self, cell_a, cell_b):
        try:
            return self.get_fpp_internal_link_by_cells(cell_a, cell_b) is not None
        except Exception:
            return False

    def _link_visual(self, cell_a, cell_b, payload):
        pair_key = self._link_pair_key(cell_a, cell_b)
        if pair_key in self._visual_link_pairs:
            return
        try:
            link = self.new_fpp_link(
                cell_a,
                cell_b,
                self._to_float(
                    payload.get("visual_link_lambda", payload.get("link_lambda", payload.get("lambda_distance", 10.0))),
                    10.0,
                ),
                self._to_float(payload.get("visual_target_distance", payload.get("target_distance", 0.0)), 0.0),
                self._to_float(payload.get("visual_max_distance", payload.get("max_distance", 0.0)), 0.0),
            )
            if link is None and not self._warned_fpp:
                print("[GeneratedCompartmentalize] FPP plugin is not loaded; visual link skipped")
                self._warned_fpp = True
            elif link is not None:
                self._visual_link_pairs.add(pair_key)
                self._visual_fpp_links_created += 1
                if not self._reported_visual_fpp_success:
                    print(
                        "[GeneratedCompartmentalize] FPP visual link active: "
                        f"created={self._visual_fpp_links_created} "
                        f"cell_a={cell_a.id} cell_b={cell_b.id}"
                    )
                    self._reported_visual_fpp_success = True
        except Exception as exc:
            if payload.get("debug") or not self._warned_fpp:
                print(f"[GeneratedCompartmentalize] Visual FPP link failed: {exc}")
                self._warned_fpp = True

    def _link_pair_key(self, cell_a, cell_b):
        return tuple(sorted((int(cell_a.id), int(cell_b.id))))

    def _maybe_report_compartment_runtime_state(self, cell, payload, mcs):
        if not (payload.get("debug") or payload.get("fpp_diagnostics")):
            return
        interval = max(1, int(self._to_float(payload.get("fpp_diagnostic_interval", 100), 100)))
        if self._last_fpp_diag_mcs >= 0 and (mcs - self._last_fpp_diag_mcs) < interval:
            return
        self._last_fpp_diag_mcs = mcs
        cluster_id = getattr(cell, "clusterId", None)
        print(
            "[GeneratedCompartmentalize] runtime state: "
            f"mcs={mcs} cell={getattr(cell, 'id', None)} cluster={cluster_id} "
            f"compartment_cells={self._compartment_cell_count(cluster_id)} "
            f"internal_links_created={self._fpp_links_created} "
            f"internal_link_inventory={self._internal_fpp_inventory_count()} "
            f"visual_links_created={self._visual_fpp_links_created} "
            f"visual_link_inventory={self._visual_fpp_inventory_count()} "
            f"hypha_length={cell.dict.get('hypha_length') if cell is not None else None} "
            f"is_tip={cell.dict.get('is_hypha_tip') if cell is not None else None}"
        )

    def _internal_fpp_inventory_count(self):
        try:
            links = self.get_focal_point_plasticity_internal_link_list()
            return len(links) if links is not None else 0
        except Exception as exc:
            if not self._warned_fpp_inventory:
                print(f"[GeneratedCompartmentalize] Could not inspect internal FPP inventory: {exc}")
                self._warned_fpp_inventory = True
            return "unavailable"

    def _visual_fpp_inventory_count(self):
        try:
            links = self.get_focal_point_plasticity_link_list()
            return len(links) if links is not None else 0
        except Exception as exc:
            if not self._warned_fpp_inventory:
                print(f"[GeneratedCompartmentalize] Could not inspect visual FPP inventory: {exc}")
                self._warned_fpp_inventory = True
            return "unavailable"

    def _compartment_cell_count(self, cluster_id):
        if cluster_id is None or self.cell_list is None:
            return "unknown"
        try:
            return sum(
                1
                for candidate in self.cell_list
                if getattr(candidate, "clusterId", None) == cluster_id
                and bool(getattr(candidate, "dict", {}).get("compartment_enabled"))
            )
        except Exception:
            return "unknown"

    def _maybe_report_hypha_summary(self, mcs):
        interval = 100
        try:
            interval = int(self._to_float(self.settings.get("hypha_summary_interval", interval), interval))
        except Exception:
            interval = 100

        if interval <= 0:
            return
        if self._last_hypha_summary_mcs >= 0 and (mcs - self._last_hypha_summary_mcs) < interval:
            return

        summary = self._hypha_summary_counts()
        hypha_total = summary["HyphaRoot"] + summary["HyphaSegment"] + summary["HyphaTip"]
        if hypha_total <= 0 and summary["AttachedFungus"] <= 0:
            return

        self._last_hypha_summary_mcs = mcs
        print(
            "[GeneratedCompartmentalize] hypha summary: "
            f"mcs={mcs} "
            f"attached={summary['AttachedFungus']} "
            f"root={summary['HyphaRoot']} "
            f"segment={summary['HyphaSegment']} "
            f"tip={summary['HyphaTip']} "
            f"active_tips={summary['active_tips']} "
            f"clusters={summary['clusters']} "
            f"expected_tree_links={summary['expected_tree_links']} "
            f"internal_links={self._internal_fpp_inventory_count()} "
            f"visual_links={self._visual_fpp_inventory_count()}"
        )

    def _hypha_summary_counts(self):
        names = ["AttachedFungus", "HyphaRoot", "HyphaSegment", "HyphaTip"]
        summary = {name: 0 for name in names}
        summary["active_tips"] = 0
        summary["clusters"] = 0
        summary["expected_tree_links"] = 0

        if self.cell_list is None:
            return summary

        type_ids = {name: self._cell_type_id(name) for name in names}
        type_id_to_name = {type_id: name for name, type_id in type_ids.items() if type_id is not None}
        hypha_type_ids = {
            type_ids.get("HyphaRoot"),
            type_ids.get("HyphaSegment"),
            type_ids.get("HyphaTip"),
        }
        hypha_type_ids.discard(None)

        clusters = set()
        for candidate in list(self.cell_list):
            name = type_id_to_name.get(getattr(candidate, "type", None))
            if not name:
                continue
            summary[name] += 1
            if getattr(candidate, "type", None) in hypha_type_ids:
                clusters.add(getattr(candidate, "clusterId", None))
            if name == "HyphaTip" and candidate.dict.get("is_hypha_tip") and not candidate.dict.get("is_dead"):
                summary["active_tips"] += 1

        clusters.discard(None)
        summary["clusters"] = len(clusters)
        hypha_total = summary["HyphaRoot"] + summary["HyphaSegment"] + summary["HyphaTip"]
        summary["expected_tree_links"] = max(0, hypha_total - summary["clusters"])
        return summary

    def _release_field(self, cell, field_info):
        if not isinstance(field_info, dict):
            return
        field_name = field_info.get("field_name")
        if not field_name or not hasattr(self.field, field_name):
            return
        amount = self._to_float(field_info.get("amount", 0.0), 0.0)
        if amount == 0:
            return
        field = getattr(self.field, field_name)
        field[int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)] += amount

    def _leak_inside_cell(self, cell, field_name, amount):
        if not self._should_leak(field_name, amount):
            return
        secretor = self.get_field_secretor(field_name)
        if secretor:
            secretor.secreteInsideCell(cell, amount)

    def _leak_at_com(self, cell, field_name, amount):
        if not self._should_leak(field_name, amount):
            return
        secretor = self.get_field_secretor(field_name)
        if secretor:
            secretor.secreteInsideCellAtCOM(cell, amount)

    def _should_leak(self, field_name, amount):
        return bool(field_name and str(field_name).strip().lower() != "none" and amount != 0)

    def _clear_non_death_state(self, cell):
        for key in ("active_force",):
            cell.dict.pop(key, None)

    def _set_death_status(self, cell, value):
        try:
            self.field.DeathStatus[cell] = value
        except Exception:
            pass

    def _clear_force(self, cell, mcs=None):
        try:
            cell.lambdaVecX = 0.0
            cell.lambdaVecY = 0.0
            cell.lambdaVecZ = 0.0
        except Exception:
            pass
        if mcs is not None:
            self._record_deactivation(cell, "force", mcs)
            self._set_metric(cell, "force", "force", 0.0)

    def _cell_by_id(self, cell_id):
        try:
            target_id = int(float(cell_id))
        except (TypeError, ValueError):
            return None
        for candidate in self.cell_list:
            if candidate.id == target_id:
                return candidate
        return None

    def _fpp_link_partners(self, cell, payload, mode):
        if mode in {"cell_id", "target_cell_id", "by_id"}:
            target = self._cell_by_id(payload.get("target_cell_id") or payload.get("partner_cell_id"))
            return [target] if target is not None else []

        partner_type = payload.get("partner_type") or payload.get("target_type") or payload.get("cell_type")
        if not partner_type:
            return []

        if mode in {"all_within_distance", "within_distance"}:
            return self._fpp_cells_by_type_within_distance(cell, partner_type, payload)

        target = self._nearest_cell_by_type_limited(cell, partner_type, payload)
        return [target] if target is not None else []

    def _create_ordinary_fpp_link(self, cell, partner, payload):
        try:
            link = self.new_fpp_link(
                cell,
                partner,
                self._to_float(payload.get("link_lambda", payload.get("lambda_distance", 10.0)), 10.0),
                self._to_float(payload.get("target_distance", 0.0), 0.0),
                self._to_float(payload.get("max_distance", 0.0), 0.0),
            )
            if link is None:
                if not self._warned_fpp:
                    print("[GeneratedFPPLink] FocalPointPlasticity plugin is not loaded; link skipped")
                    self._warned_fpp = True
                return False
            self._rule_fpp_links_created += 1
            return True
        except Exception as exc:
            if payload.get("debug") or not self._warned_fpp:
                print(f"[GeneratedFPPLink] Failed to create FPP link: {exc}")
                self._warned_fpp = True
            return False

    def _fpp_link_exists(self, cell, partner):
        try:
            return self.get_fpp_link_by_cells(cell, partner) is not None
        except Exception:
            return False

    def _nearest_cell_by_type_limited(self, cell, type_name, payload):
        type_id = self._cell_type_id(type_name)
        if type_id is None:
            return None
        max_distance = self._to_float(payload.get("max_search_distance", payload.get("search_radius", 0.0)), 0.0)
        max_dist_sq = max_distance * max_distance if max_distance > 0 else None
        best = None
        best_dist = float("inf")
        for candidate in self.cell_list_by_type(type_id):
            if candidate.id == cell.id or candidate.dict.get("is_dead"):
                continue
            distance = (candidate.xCOM - cell.xCOM) ** 2 + (candidate.yCOM - cell.yCOM) ** 2 + (candidate.zCOM - cell.zCOM) ** 2
            if max_dist_sq is not None and distance > max_dist_sq:
                continue
            if distance < best_dist:
                best = candidate
                best_dist = distance
        return best

    def _fpp_cells_by_type_within_distance(self, cell, type_name, payload):
        type_id = self._cell_type_id(type_name)
        if type_id is None:
            return []
        max_distance = self._to_float(payload.get("max_search_distance", payload.get("search_radius", 0.0)), 0.0)
        if max_distance <= 0:
            return []
        max_links = int(self._to_float(payload.get("max_links", 1), 1))
        max_dist_sq = max_distance * max_distance
        candidates = []
        for candidate in self.cell_list_by_type(type_id):
            if candidate.id == cell.id or candidate.dict.get("is_dead"):
                continue
            distance = (candidate.xCOM - cell.xCOM) ** 2 + (candidate.yCOM - cell.yCOM) ** 2 + (candidate.zCOM - cell.zCOM) ** 2
            if distance <= max_dist_sq:
                candidates.append((distance, candidate))
        candidates.sort(key=lambda item: item[0])
        return [candidate for _, candidate in candidates[:max_links]]

    def _nearest_cell_by_type(self, cell, type_name):
        type_id = self._cell_type_id(type_name)
        if type_id is None:
            return None
        best = None
        best_dist = float("inf")
        for candidate in self.cell_list_by_type(type_id):
            if candidate.id == cell.id:
                continue
            distance = (candidate.xCOM - cell.xCOM) ** 2 + (candidate.yCOM - cell.yCOM) ** 2 + (candidate.zCOM - cell.zCOM) ** 2
            if distance < best_dist:
                best = candidate
                best_dist = distance
        return best

    def _nearest_cell_by_types(self, cell, type_names):
        if isinstance(type_names, str):
            type_names = [part.strip() for part in type_names.split(",") if part.strip()]
        elif isinstance(type_names, (list, tuple, set)):
            type_names = [str(part).strip() for part in type_names if str(part).strip()]
        elif type_names:
            type_names = [str(type_names).strip()]
        else:
            type_names = []

        best = None
        best_dist = float("inf")
        for type_name in type_names:
            type_id = self._cell_type_id(type_name)
            if type_id is None:
                continue
            for candidate in self.cell_list_by_type(type_id):
                if candidate.id == cell.id or candidate.dict.get("is_dead"):
                    continue
                distance = (candidate.xCOM - cell.xCOM) ** 2 + (candidate.yCOM - cell.yCOM) ** 2 + (candidate.zCOM - cell.zCOM) ** 2
                if distance < best_dist:
                    best = candidate
                    best_dist = distance
        return best

    def _dict_number(self, cell, key, default):
        if key in cell.dict:
            return self._to_float(cell.dict.get(key), default)
        state = cell.dict.get("state", {})
        if isinstance(state, dict) and key in state:
            return self._to_float(state.get(key), default)
        return default

    def _normalize(self, vector):
        x, y, z = vector
        norm = math.sqrt(x * x + y * y + z * z)
        if norm <= 0.0 or not math.isfinite(norm):
            return None
        return (x / norm, y / norm, z / norm)

    def _clamp_index(self, value, upper):
        if upper <= 1:
            return 0
        return max(0, min(upper - 1, int(round(value))))

    def _to_float(self, value, default=0.0):
        if value in (None, ""):
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _as_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def _flatten_cell_dict(self, data, parent_key="", sep="_"):
        items = []
        if not isinstance(data, dict):
            return {}
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
            if isinstance(value, dict):
                items.extend(self._flatten_cell_dict(value, new_key, sep=sep).items())
            else:
                items.append((new_key, value))
        return dict(items)

    def _ensure_behaviour_stats(self, cell):
        return cell.dict.setdefault("behaviour_stats", {})

    def _behaviour_stats(self, cell, behaviour):
        return self._ensure_behaviour_stats(cell).setdefault(behaviour, {})

    def _record_event(self, cell, behaviour, mcs, amount=None):
        stats = self._behaviour_stats(cell, behaviour)
        previous_mcs = stats.get("last_mcs")
        stats["count"] = stats.get("count", 0) + 1
        stats.setdefault("first_mcs", mcs)
        stats["last_mcs"] = mcs
        stats["interval_since_last"] = None if previous_mcs is None else mcs - previous_mcs
        if amount is not None:
            stats["last_delta"] = amount
            stats["total_delta"] = stats.get("total_delta", 0.0) + amount
        return stats

    def _sync_event_count(self, cell, behaviour, mcs, count):
        stats = self._behaviour_stats(cell, behaviour)
        previous_mcs = stats.get("last_mcs")
        stats["count"] = count
        if count:
            stats.setdefault("first_mcs", mcs)
            stats["last_mcs"] = mcs
            stats["interval_since_last"] = None if previous_mcs is None else mcs - previous_mcs
        return stats

    def _record_activation(self, cell, behaviour, mcs):
        stats = self._behaviour_stats(cell, behaviour)
        if not stats.get("active", False):
            stats["active"] = True
            stats["active_since_mcs"] = mcs
            stats["activation_count"] = stats.get("activation_count", 0) + 1
        stats["last_active_mcs"] = mcs
        return stats

    def _record_active_step(self, cell, behaviour, mcs, delta=None):
        stats = self._record_activation(cell, behaviour, mcs)
        stats["last_active_mcs"] = mcs
        stats["active_duration"] = stats.get("active_duration", 0) + 1
        stats["inactive_duration"] = 0
        if delta is not None:
            stats["last_delta"] = delta
            stats["total_delta"] = stats.get("total_delta", 0.0) + delta
        return stats

    def _record_deactivation(self, cell, behaviour, mcs):
        stats = self._behaviour_stats(cell, behaviour)
        if stats.get("active", False):
            stats["active"] = False
            stats["deactivated_mcs"] = mcs
            last_active = stats.get("last_active_mcs", stats.get("active_since_mcs"))
            if last_active is not None:
                stats["inactive_duration"] = mcs - last_active
        return stats

    def _record_field_delta(self, cell, behaviour, field_name, mcs, delta):
        parent = self._behaviour_stats(cell, behaviour)
        stats = parent.setdefault(str(field_name), {})
        previous_mcs = stats.get("last_active_mcs")
        if not stats.get("active", False):
            stats["active"] = True
            stats["active_since_mcs"] = mcs
            stats["activation_count"] = stats.get("activation_count", 0) + 1
        stats["last_active_mcs"] = mcs
        stats["interval_since_last"] = None if previous_mcs is None else mcs - previous_mcs
        stats["active_duration"] = stats.get("active_duration", 0) + 1
        stats["last_delta"] = delta
        stats["total_delta"] = stats.get("total_delta", 0.0) + delta
        return stats

    def _set_metric(self, cell, behaviour, key, value):
        stats = self._behaviour_stats(cell, behaviour)
        stats[key] = value
        return stats

    def _execute_custom_script(self, rule):
        payload = self._case_payload(rule.get("cases", [{}])[0]) if rule.get("cases") else {}
        script_path = payload.get("script_path") or rule.get("custom_script")
        if not script_path:
            return False
        path = self._resolve_script_path(script_path)
        if not path.exists():
            print(f"[GeneratedCustomScript] Script not found: {path}")
            return False
        try:
            if path not in self._script_cache:
                spec = importlib.util.spec_from_file_location("generated_custom_rule", path)
                if spec is None or spec.loader is None:
                    return False
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._script_cache[path] = module
            module = self._script_cache[path]
            if hasattr(module, "match") and not module.match(self):
                return False
            if hasattr(module, "run"):
                module.run(self, payload.get("apply_params", {}))
                return True
        except Exception as exc:
            print(f"[GeneratedCustomScript] Failed: {exc}")
        return False


    def update_attributes(self):
        parent = self.parent_cell
        child = self.child_cell
        request = self._current_division_request or parent.dict.get("_division_request", {})
        state_key = request.get("state_key", "division_count")
        strategy = request.get("inheritance_strategy", "total")
        mcs = getattr(self, "current_mcs", 0)
        parent_type = request.get("parent_type") or self.get_type_name_by_cell(parent)
        child_type = request.get("child_type") or parent_type

        parent.dict[state_key] = parent.dict.get(state_key, 0) + 1

        if strategy == "reset":
            self.clone_attributes(source_cell=parent, target_cell=child, no_clone_key_dict_list=[state_key])
            child.dict[state_key] = 0
        else:
            self.clone_parent_2_child()
            child.dict[state_key] = parent.dict[state_key]

        if parent_type:
            type_id = self._cell_type_id(parent_type)
            if type_id is not None:
                parent.type = type_id
            self._apply_celltype_constraints(parent, parent_type)
        if child_type:
            type_id = self._cell_type_id(child_type)
            if type_id is not None:
                child.type = type_id
            self._apply_celltype_constraints(child, child_type)

        self._sync_event_count(parent, "division", mcs, parent.dict.get(state_key, 0))
        self._sync_event_count(child, "division", mcs, child.dict.get(state_key, 0))
        self._set_metric(parent, "division", "state_key", state_key)
        self._set_metric(child, "division", "state_key", state_key)

        for key in ["phago_count", "absorbed_cargo", "internal_drug_concentration"]:
            if key in parent.dict:
                old_value = parent.dict[key]
                parent.dict[key] = old_value / 2.0
                child.dict[key] = old_value / 2.0

        for cell in [parent, child]:
            cell.dict.setdefault("_internal", {})["division_in_progress"] = False
            cell.dict["_internal"]["division_request"] = None
        self._current_division_request = {}

    # === USER CUSTOM HOOKS START ===
    # Add optional override methods here. This block is preserved when the
    # generator rewrites this file.
    #
    # Per-rule hook:
    # def rule_1_copy(self, cell, payload, mcs):
    #     return True
    #
    # Per-behaviour hook:
    # def handle_secrete_uptake(self, cell, payload, mcs):
    #     return "default"  # fall back to generated behaviour
    # === USER CUSTOM HOOKS END ===

SimulationSteppable = Candida_albicans_zebrafishSteppable