#!/usr/bin/env python3

import argparse
import csv
import os
import sys
import hashlib
import json
import re
import datetime
from collections import defaultdict
from anytree import Node
import html

def build_tree(files):
    roots = {}
    nodes = {}

    for file in files:
        unc = file['unc']
        # Remove leading double backslashes for building the tree structure
        if unc.startswith('\\\\'):
            unc = unc[2:]
        parts = unc.split('\\')
        if len(parts) < 2:
            continue  # invalid path

        share_host = parts[0]
        if share_host not in roots:
            roots[share_host] = Node(share_host, type='server')
            nodes[share_host] = roots[share_host]

        parent_path = share_host
        for part in parts[1:-1]:  # intermediate folders
            current_path = parent_path + '\\' + part
            if current_path not in nodes:
                nodes[current_path] = Node(part, parent=nodes[parent_path])
            parent_path = current_path

        file_name = parts[-1]
        current_path = parent_path + '\\' + file_name
        if current_path not in nodes:
            # Attach the data (file info) to a leaf node
            nodes[current_path] = Node(
                file_name,
                parent=nodes[parent_path],
                data=file
            )

    return list(roots.values())


def build_jstree(nodes):
    jstree_nodes = []
    for node in nodes:
        node_dict = {
            'text': html.escape(node.name),
            'children': build_jstree(node.children),
            'type': getattr(node, 'type', 'default')
        }

        # If node is a file node, add the file data
        if hasattr(node, 'data'):
            node_dict['data'] = node.data
            # Force the file icon for leaves
            node_dict['type'] = 'file'
        jstree_nodes.append(node_dict)
    return jstree_nodes


def generate_tree_html(jstree_data, outputname, out_dir):
    quick_filter_buttons = {
        "Office Docs": r"\.(doc|xls|ppt|docx|xlsx|pptx)$",
        "Password Filenames": r"password|pwd|cred|creds|credentials",
        "Medical Records": r"medical|patient|hipaa|health",
        "Financial Data": r"financial|invoice|receipt|accounting",
        "Configuration Files": r"\.(config|conf|cfg|ini|xml|json|yaml|yml)$",
        "Log Files": r"\.(log|txt)$",
        "Database Files": r"\.(db|sqlite|sql|mdf|sdf|dat|accdb)$",
        "Email Files": r"\.(pst|ost|eml|msg)$",
        "Certificate Files": r"\.(pem|crt|cer|pfx|p12|key)$",
        "Source Code Files": r"\.(py|js|java|c|cpp|ts|rb|go|php|sh|bat)$",
        "Key Files": r"(pem|ppk|key|ssh)",
        "Reset Filters": ""
    }

    quick_filters_html = '<div class="quick-filters-header">Quick Filters</div>\n'
    for name, pattern in quick_filter_buttons.items():
        quick_filters_html += f'<button class="qf-btn" data-pattern="{pattern}">{name}</button>\n'

    tree_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Parsler - Tree View</title>
        <!-- jsTree CSS -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.12/themes/default/style.min.css" />
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #2e2e2e;
                color: #e0e0e0;
                padding: 20px;
                position: relative;
                font-size: 14px;
            }}
            #jstree {{
                margin-top: 20px;
            }}
            .control-buttons {{
                margin-bottom: 10px;
            }}
            .control-buttons button {{
                margin-right: 10px;
                padding: 6px 12px;
                background-color: #444;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }}
            .control-buttons button:hover {{
                background-color: #555;
            }}
            .highlight {{
                background-color: yellow !important;
            }}
            .quick-filters {{
                margin-bottom: 10px;
            }}
            .quick-filters-header {{
                font-size: 16px;
                margin-bottom: 8px;
                color: #ffd760;
            }}
            .qf-btn {{
                margin-right: 8px;
                margin-bottom: 8px;
                padding: 5px 10px;
                background-color: #444;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }}
            .qf-btn:hover {{
                background-color: #555;
            }}

            .file-info-inline {{
                margin-top: 10px;
                background-color: #1e1e1e;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 10px;
            }}
            .file-info-inline h2 {{
                color: #ffd760;
                margin-top: 0;
                font-size: 16px;
            }}
            .file-info-inline table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 8px;
                font-size: 13px;
            }}
            .file-info-inline th, .file-info-inline td {{
                border: 1px solid #555;
                padding: 6px;
                word-wrap: break-word;
                white-space: normal;
            }}
            .file-info-inline th {{
                background-color: #444;
                color: #e0e0e0;
            }}

            /* Navigation Tabs */
            .nav-tabs {{
                overflow: hidden;
                background-color: #1e1e1e;
                margin-bottom: 20px;
                border-radius: 5px;
                position: relative;
            }}
            .nav-tabs a {{
                float: left;
                display: block;
                color: #e0e0e0;
                text-align: center;
                padding: 10px 14px;
                text-decoration: none;
                transition: background-color 0.3s;
                border-right: 1px solid #555;
                font-size: 14px;
            }}
            .nav-tabs a:last-child {{
                border-right: none;
            }}
            .nav-tabs a:hover {{
                background-color: #555;
            }}
            .nav-tabs a.active {{
                background-color: #555;
            }}

            /* jstree search highlight */
            .jstree-default .jstree-search {{
                background-color: yellow !important;
                font-style: normal;
                color: #000;
                font-weight: bold;
            }}

            /* Selected and hovered states for jsTree items */
            .jstree-clicked {{
                background-color: #5b5d5e !important;
                color: #ffffff !important;
            }}
            .jstree-anchor:hover {{
                background-color: #6b6d6f !important;
                color: #ffffff !important;
            }}

            /* Updated styling for the search input (matching main page) */
            #search-input {{
                width: 300px;
                padding: 5px;
                margin-right: 20px;
                background-color: #444;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                box-sizing: border-box;
            }}
            #search-input::placeholder {{
                color: #cccccc;
            }}
        </style>
        <!-- jQuery -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
        <!-- jsTree JS -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.12/jstree.min.js"></script>
        <script src="tree_data.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                $('#jstree').jstree({{
                    'core': {{
                        'data': PARSLER_TREE_DATA,
                        'check_callback': true
                    }},
                    // Use search plugin with custom callback for real regex,
                    // but do NOT hide non-matching nodes:
                    'plugins': ['search', 'types'],
                    'types': {{
                        'default': {{ 'icon': 'jstree-folder' }},
                        'server':  {{ 'icon': 'https://img.icons8.com/ios-filled/16/ffffff/server.png' }},
                        'file':    {{ 'icon': 'jstree-file' }}
                    }},
                    'search': {{
                        'show_only_matches': false,
                        'close_opened_onclear': false,
                        'search_callback': function(pat, node) {{
                            if(!pat) return true; // If no search term, show all
                            try {{
                                // Attempt a case-insensitive regex
                                var regex = new RegExp(pat, 'i');
                                return regex.test(node.text);
                            }} catch(e) {{
                                // Fallback to plain substring if invalid regex
                                return node.text.toLowerCase().indexOf(pat.toLowerCase()) >= 0;
                            }}
                        }}
                    }}
                }});

                var to = false;
                function performSearch(v) {{
                    if(to) {{ clearTimeout(to); }}
                    to = setTimeout(function () {{
                        $('#jstree').jstree(true).search(v);
                    }}, 250);
                }}

                $('#search-input').keyup(function () {{
                    var v = $('#search-input').val();
                    performSearch(v);
                }});

                // Collapse all before applying quick filter
                $('.qf-btn').on('click', function() {{
                    $('#jstree').jstree('close_all');
                    var pattern = $(this).data('pattern');
                    $('#search-input').val(pattern);
                    performSearch(pattern);
                }});

                // Display details inline below the clicked file
                $('#jstree').on('select_node.jstree', function(e, data) {{
                    var node = data.node;
                    var $li = $('#' + node.id);

                    // If details are already open for this node, close them
                    if ($li.find('> .file-info-inline').length > 0) {{
                        $li.find('> .file-info-inline').remove();
                        return;
                    }}

                    // Remove any opened details from other nodes
                    $('.file-info-inline').remove();

                    // Insert details inline if node has data
                    if (node.data) {{
                        function escapeHtml(str) {{
                            if (!str) return '';
                            return str
                              .replace(/&/g, "&amp;")
                              .replace(/</g, "&lt;")
                              .replace(/>/g, "&gt;")
                              .replace(/"/g, "&quot;")
                              .replace(/'/g, "&#039;");
                        }}

                        var severity = escapeHtml(node.data.severity) || 'N/A';
                        var rule = escapeHtml(node.data.rule) || 'N/A';
                        var keyword = escapeHtml(node.data.keyword) || 'N/A';
                        var modified = escapeHtml(node.data.modified) || 'N/A';
                        var unc = escapeHtml(node.data.unc) || 'N/A';
                        var extension = escapeHtml(node.data.extension) || 'N/A';
                        var content = escapeHtml(node.data.content) || 'N/A';

                        var infoHtml = `
                            <div class="file-info-inline">
                                <h2>File Information</h2>
                                <table>
                                    <tr><th>Severity</th><td>${{severity}}</td></tr>
                                    <tr><th>Rule</th><td>${{rule}}</td></tr>
                                    <tr><th>Keyword</th><td>${{keyword}}</td></tr>
                                    <tr><th>Modified</th><td>${{modified}}</td></tr>
                                    <tr><th>UNC Path</th><td>${{unc}}</td></tr>
                                    <tr><th>Extension</th><td>${{extension}}</td></tr>
                                    <tr><th>Content</th><td>${{content}}</td></tr>
                                </table>
                            </div>
                        `;
                        $li.children('a').after(infoHtml);
                    }}
                }});

                document.getElementById('expand-all').addEventListener('click', function() {{
                    $('#jstree').jstree('open_all');
                }});

                document.getElementById('collapse-all').addEventListener('click', function() {{
                    $('#jstree').jstree('close_all');
                }});
            }});
        </script>
    </head>
    <body>
        <!-- Navigation Tabs -->
        <div class="nav-tabs">
            <a href="full.html" class="tab-link">Main Report</a>
            <a href="tree.html" class="tab-link active">Tree View</a>
            <a href="stats.html" class="tab-link">Stats</a>
            <a href="help.html" class="tab-link">Help</a>
        </div>

        <h1>Parsler - Tree View</h1>

        <div class="quick-filters">
            {quick_filters_html}
        </div>

        <div class="control-buttons">
            <input type="text" id="search-input" placeholder="Regex search..." />
            <button id="expand-all">Expand All</button>
            <button id="collapse-all">Collapse All</button>
        </div>

        <div id="jstree"></div>

        <p><a href="full.html">Back to Main Report</a></p>
    </body>
    </html>
    """

    tree_data_file = os.path.join(out_dir, "tree_data.js")
    print(f"Saving: {tree_data_file}")
    with open(tree_data_file, 'w', encoding='utf-8') as f:
        f.write('const PARSLER_TREE_DATA=')
        json.dump(jstree_data, f)
        f.write(';\n')

    filename = os.path.join(out_dir, "tree.html")
    print(f"Saving: {filename}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(tree_html)




def export_stats_html(
    stats, 
    top_rules, 
    top_hosts,
    all_rules_sorted,
    share_counts,
    top_extensions,
    files_by_month,
    outputname, 
    out_dir
):
    sorted_months = sorted(files_by_month.keys())
    month_labels = sorted_months
    month_counts = [files_by_month[m] for m in sorted_months]

    rules_table = ""
    for rule, count in all_rules_sorted:
        rules_table += f"<tr><td>{html.escape(rule)}</td><td>{count}</td></tr>"

    extension_table = ""
    for e, c in top_extensions:
        extension_table += f"<tr><td>{html.escape(e)}</td><td>{c}</td></tr>"

    share_table_rows = ""
    for share, count in sorted(share_counts.items(), key=lambda x: x[1], reverse=True):
        share_table_rows += f"<tr><td>{html.escape(share)}</td><td>{count}</td></tr>"

    stats_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Parsler - Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #2e2e2e;
                color: #e0e0e0;
                padding: 20px;
                position: relative;
                font-size: 14px;
            }}
            a {{
                color: #1e90ff;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .nav-tabs {{
                overflow: hidden;
                background-color: #1e1e1e;
                margin-bottom: 20px;
                border-radius: 5px;
            }}
            .nav-tabs a {{
                float: left;
                display: block;
                color: #e0e0e0;
                text-align: center;
                padding: 10px 14px;
                text-decoration: none;
                transition: background-color 0.3s;
                border-right: 1px solid #555;
                font-size: 14px;
            }}
            .nav-tabs a:last-child {{
                border-right: none;
            }}
            .nav-tabs a:hover {{
                background-color: #555;
            }}
            .nav-tabs a.active {{
                background-color: #555;
            }}
            .chart-row {{
                display: flex;
                flex-wrap: wrap;
                margin-bottom: 40px;
                gap: 20px;
            }}
            .chart-container {{
                flex: 1 1 45%;
                background-color: #1e1e1e;
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #444;
                min-width: 250px;
            }}
            .pie-chart-container {{
                flex: 0 0 auto;
                width: 350px;
                background-color: #1e1e1e;
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #444;
            }}
            h1 {{
                text-align: left;
                color: #ffffff;
            }}
            .table-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                margin-top: 40px;
            }}
            table.stat-table {{
                border-collapse: collapse;
                background-color: #1e1e1e;
                border: 1px solid #444;
                border-radius: 5px;
                font-size: 14px;
                min-width: 200px;
                margin-bottom: 20px;
            }}
            table.stat-table th, table.stat-table td {{
                border: 1px solid #555;
                padding: 8px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                line-height: 1.4em;
                height: 1.4em;
            }}
            table.stat-table th {{
                background-color: #444;
            }}
            table.stat-table caption {{
                color: #ffd760;
                font-size: 16px;
                margin-bottom: 6px;
                caption-side: top;
                text-align: left;
            }}
            @media (max-width: 800px) {{
                .chart-container, .pie-chart-container {{
                    flex: 1 1 100%;
                    margin-bottom: 20px;
                }}
                .table-row {{
                    display: block;
                }}
                table.stat-table {{
                    width: 100%;
                    margin-bottom: 20px;
                }}
            }}
        </style>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                // -- Pie chart: Severity --
                const severityCtx = document.getElementById('severityChart').getContext('2d');
                new Chart(severityCtx, {{
                    type: 'pie',
                    data: {{
                        labels: {json.dumps(list(stats['findings_by_severity'].keys()))},
                        datasets: [{{
                            data: {json.dumps(list(stats['findings_by_severity'].values()))},
                            backgroundColor: ['#292929', '#e92929', '#ffcd00', '#99e699']
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Severity Distribution',
                                color: '#ffffff'
                            }},
                            legend: {{
                                labels: {{
                                    color: '#e0e0e0'
                                }}
                            }}
                        }}
                    }}
                }});

                // -- Bar chart: Findings Over Time --
                const filesByMonthCtx = document.getElementById('filesByMonthChart').getContext('2d');
                new Chart(filesByMonthCtx, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps(month_labels)},
                        datasets: [{{
                            label: 'Findings',
                            data: {json.dumps(month_counts)},
                            backgroundColor: '#00D084'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Findings Over Time (by Last Modified Date)',
                                color: '#ffffff'
                            }},
                            legend: {{
                                labels: {{
                                    color: '#e0e0e0'
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{
                                    color: '#e0e0e0'
                                }},
                                grid: {{
                                    color: '#555555'
                                }}
                            }},
                            x: {{
                                ticks: {{
                                    color: '#e0e0e0'
                                }},
                                grid: {{
                                    color: '#555555'
                                }}
                            }}
                        }}
                    }}
                }});

                // -- Bar chart: Top 5 Rules --
                const rulesCtx = document.getElementById('rulesChart').getContext('2d');
                new Chart(rulesCtx, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps([rule for rule, count in top_rules])},
                        datasets: [{{
                            label: 'Count',
                            data: {json.dumps([count for rule, count in top_rules])},
                            backgroundColor: '#FF6384'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Top 5 Detection Rules',
                                color: '#ffffff'
                            }},
                            legend: {{
                                labels: {{
                                    color: '#e0e0e0'
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{
                                    color: '#e0e0e0'
                                }},
                                grid: {{
                                    color: '#555555'
                                }}
                            }},
                            x: {{
                                ticks: {{
                                    color: '#e0e0e0'
                                }},
                                grid: {{
                                    color: '#555555'
                                }}
                            }}
                        }}
                    }}
                }});

                // -- Bar chart: Top 5 Hosts --
                const hostsCtx = document.getElementById('hostsChart').getContext('2d');
                new Chart(hostsCtx, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps([host for host, count in top_hosts])},
                        datasets: [{{
                            label: 'Count',
                            data: {json.dumps([count for host, count in top_hosts])},
                            backgroundColor: '#36A2EB'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Top 5 Hosts',
                                color: '#ffffff'
                            }},
                            legend: {{
                                labels: {{
                                    color: '#e0e0e0'
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{
                                    color: '#e0e0e0'
                                }},
                                grid: {{
                                    color: '#555555'
                                }}
                            }},
                            x: {{
                                ticks: {{
                                    color: '#e0e0e0'
                                }},
                                grid: {{
                                    color: '#555555'
                                }}
                            }}
                        }}
                    }}
                }});
            }});
        </script>
    </head>
    <body>
        <!-- Navigation Tabs -->
        <div class="nav-tabs">
            <a href="full.html" class="tab-link">Main Report</a>
            <a href="tree.html" class="tab-link">Tree View</a>
            <a href="stats.html" class="tab-link active">Stats</a>
            <a href="help.html" class="tab-link">Help</a>
        </div>

        <h1>Parsler - Stats</h1>

        <div class="chart-row">
            <div class="pie-chart-container">
                <canvas id="severityChart" style="width:100%; height:300px;"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="filesByMonthChart" style="width:100%; height:300px;"></canvas>
            </div>
        </div>

        <div class="chart-row">
            <div class="chart-container">
                <canvas id="rulesChart" style="width:100%; height:300px;"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="hostsChart" style="width:100%; height:300px;"></canvas>
            </div>
        </div>

        <div class="table-row">
            <table class="stat-table">
                <caption>Findings by Share</caption>
                <tr><th>Share</th><th>Count</th></tr>
                {share_table_rows}
            </table>

            <table class="stat-table">
                <caption>All Rules That Matched</caption>
                <tr><th>Rule</th><th>Count</th></tr>
                {rules_table}
            </table>

            <table class="stat-table">
                <caption>Top Extensions</caption>
                <tr><th>Extension</th><th>Count</th></tr>
                {extension_table}
            </table>
        </div>

        <p style="margin-top:40px;">
            <a href="full.html">Back to Main Report</a>
        </p>
    </body>
    </html>
    """

    filename = os.path.join(out_dir, "stats.html")
    print(f"Saving: {filename}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(stats_html)


def export_help_html(out_dir):
    """
    Writes the help.html file to the output directory
    """
    help_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Snaffler Help</title>
    <style>
        body {
            background-color: #2e2e2e;
            color: #e0e0e0;
            font-family: Arial, sans-serif;
            padding: 20px;
            font-size: 14px;
        }
        h1, h2, h3 {
            color: #ffffff;
        }
        h1 {
            font-weight: bold;
            margin-bottom: 20px;
            text-align: left;
        }
        h2 {
            font-size: 22px;
            font-weight: bold;
            margin-top: 30px;
            border-bottom: 1px solid #555;
            padding-bottom: 5px;
        }
        h3 {
            font-size: 20px;
            margin-top: 20px;
        }
        p {
            line-height: 1.6;
        }
        ul {
            list-style: disc;
            padding-left: 20px;
        }
        a {
            color: #1e90ff;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .nav-tabs {
            overflow: hidden;
            background-color: #1e1e1e;
            margin-bottom: 20px;
            border-radius: 5px;
        }
        .nav-tabs a {
            float: left;
            display: block;
            color: #e0e0e0;
            text-align: center;
            padding: 10px 14px;
            text-decoration: none;
            transition: background-color 0.3s;
            border-right: 1px solid #555;
        }
        .nav-tabs a:last-child {
            border-right: none;
        }
        .nav-tabs a:hover {
            background-color: #555;
        }
        .nav-tabs a.active {
            background-color: #555;
        }
    </style>
</head>
<body>
    <!-- Navigation Tabs -->
    <div class="nav-tabs">
        <a href="full.html" class="tab-link">Main Report</a>
        <a href="tree.html" class="tab-link">Tree View</a>
        <a href="stats.html" class="tab-link">Stats</a>
        <a href="help.html" class="tab-link active">Help</a>
    </div>

    <h1>Parsler Help</h1>

    <h2>Overview of Parsler Pages</h2>
    <p>These pages are designed to help review findings from the Snaffler output in an organized and user-friendly format:</p>
    <ul>
        <li><strong><a href="full.html">Main Report:</a></strong> A comprehensive tabular view of all findings, including file details, severity levels, and filtering options.</li>
        <li><strong><a href="tree.html">Tree View:</a></strong> A hierarchical structure of the findings for easier navigation of file shares and directories.</li>
        <li><strong><a href="stats.html">Stats:</a></strong> Visual analytics with charts and summaries to highlight key findings and trends.</li>
    </ul>

    <h2>What is Snaffler?</h2>
    <p>
        Snaffler is an open-source tool designed to identify potentially sensitive files on network file shares. 
        By analyzing file metadata and content, it helps organizations detect data leakage risks and mitigate vulnerabilities in their file storage systems.
        <br>For more information about Snaffler, visit the <a href="https://github.com/SnaffCon/Snaffler">official GitHub repository</a>.
    </p>

    <h2>How to Use the Main Report Page</h2>
    <p>The Main Report page offers a detailed view of all findings. Key features include:</p>
    <ul>
        <li><strong>Search:</strong> Filter results using keywords or regular expressions in the search bar.</li>
        <li><strong>Filters:</strong> Apply column-specific filters for attributes like severity or file extension.</li>
        <li><strong>Export:</strong> Save filtered results as CSV or JSON for offline analysis.</li>
        <li><strong>Sorting:</strong> Sort by clicking on column headers (e.g., severity or modified date).</li>
    </ul>

    <h2>How to Use the Tree View Page</h2>
    <p>The Tree View page provides a hierarchical representation of the file shares. Features include:</p>
    <ul>
        <li><strong>Expandable Folders:</strong> Click on folders to navigate through their contents.</li>
        <li><strong>Inline File Details:</strong> View additional information about a file directly beneath it by clicking on the file name.</li>
        <li><strong>Quick Filters:</strong> Highlight specific types of files (e.g., Office documents or password files) using pre-configured filters.</li>
        <li><strong>Search:</strong> Enter a keyword or regex to locate matching files or folders.</li>
    </ul>

    <h2>Why Are These Files Sensitive?</h2>
    <p>
        Snaffler flags files based on specific patterns and attributes that indicate potential sensitivity. 
        This can include file names with keywords like "password" or "credential," file extensions often used for configs or database backups, 
        or file content containing possible passwords, PII, or other secrets. A full listing of default rules built into Snaffler can be found in the <a href="https://github.com/SnaffCon/Snaffler/tree/master/Snaffler/SnaffRules/DefaultRules">Snaffler repo</a>.
    </p>
    <p>
        Some flagged files may be false positives. For example, "passwords_example.txt" might be a documentation file rather than a real credential store.
    </p>

    <h2>Best Practices for Analysis</h2>
    <p>When analyzing the parsed Snaffler results, consider these tips:</p>
    <ul>
        <li><strong>Prioritize High Severity Files:</strong> Focus on files flagged as “Black" or "Red” first.</li>
        <li><strong>Leverage Quick Filters:</strong> Use pre-configured filters to isolate files of interest quickly.</li>
        <li><strong>Review Permissions:</strong> Check the ACLs on sensitive files for misconfigurations. Sometimes these files are where they should be but don't have ACLs configured properly.</li>
    </ul>
</body>
</html>
"""
    filename = os.path.join(out_dir, "help.html")
    print(f"Saving: {filename}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(help_html)


def export_data_js(objects, out_dir):
    keys = ['severity', 'rule', 'keyword', 'modified', 'extension', 'unc', 'content']
    rows = [[html.unescape(obj.get(k) or '') for k in keys] for obj in objects]
    filename = os.path.join(out_dir, 'data.js')
    print(f"Saving: {filename}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('const PARSLER_KEYS=')
        json.dump(keys, f)
        f.write(';\nconst PARSLER_DATA=')
        json.dump(rows, f)
        f.write(';\n')


def export_full_html(out_dir):
    js = r"""
const PAGE_SIZE = 500;
let filteredData = [], sortCol = null, sortDir = 'asc', currentPage = 0;
let SEARCH_INDEX = null;
let searchId = 0;
const SEV_ORDER = {Black:0, Red:1, Yellow:2, Green:3};

const QUICK_FILTERS = [
    {name:'Office Docs',          col:4, val:String.raw`\.(doc|xls|ppt|docx|xlsx|pptx)$`},
    {name:'Password Filenames',   col:1, val:'password|pwd|cred'},
    {name:'Connection Strings',   col:2, val:'connectionstring'},
    {name:'SA Account',           col:6, val:String.raw`\\?["']?sa\\?["']?`},
    {name:'Connection String PW', col:6, val:';Password='},
    {name:'Config Files',         col:4, val:String.raw`\.(config|conf|cfg|ini|xml|json|yaml|yml)$`},
    {name:'Log Files',            col:4, val:String.raw`\.(log|txt)$`},
    {name:'Backup Files',         col:4, val:String.raw`\.(bak|backup|old|tmp)$`},
    {name:'Database Files',       col:4, val:String.raw`\.(db|sqlite|sql|mdf|sdf|dat|accdb)$`},
    {name:'Email Files',          col:4, val:String.raw`\.(pst|ost|eml|msg)$`},
    {name:'Certificate Files',    col:4, val:String.raw`\.(pem|crt|cer|pfx|p12|key)$`},
    {name:'Source Code',          col:4, val:String.raw`\.(py|js|java|c|cpp|ts|rb|go|php|sh|bat)$`},
    {name:'Key Files',            col:4, val:String.raw`\.(pem|ppk|key|ssh)$`},
    {name:'Financial Data',       col:5, val:'financial|invoice|receipt'},
    {name:'Private Keys',         col:6, val:'PRIVATE KEY'},
    {name:'Health Records',       col:6, val:'(hipaa|medical|patient)'},
    {name:'Archived Files',       col:4, val:String.raw`\.(zip|tar|gz|7z|rar|iso)$`},
    {name:'Reset Filters',        col:null, val:null},
];

function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function highlightText(raw, re) {
    if (!re || !raw) return esc(raw || '');
    re = new RegExp(re.source, (re.flags || 'g').replace(/g/g, '') + 'g');
    let result = '', last = 0, m;
    while ((m = re.exec(raw)) !== null) {
        result += esc(raw.slice(last, m.index)) + '<mark>' + esc(m[0]) + '</mark>';
        last = m.index + m[0].length;
        if (m[0].length === 0) { re.lastIndex++; break; }
    }
    return result + esc(raw.slice(last));
}

function makeRe(s, flags) {
    if (!s) return null;
    try { return new RegExp(s, flags || 'i'); } catch(e) { return null; }
}

function getColInputs() {
    return [...document.querySelectorAll('.filter-row input,.filter-row select')];
}

function getFilters() {
    return {
        search: document.getElementById('search-input').value.trim(),
        cols: getColInputs().map(el => el.value.trim())
    };
}

function showStatus(msg, busy) {
    const el = document.getElementById('search-status');
    el.textContent = msg;
    el.classList.toggle('busy', !!busy);
}

let filterTimer = null;
function scheduleFilter() {
    if (filterTimer) clearTimeout(filterTimer);
    filterTimer = setTimeout(applyFilters, 300);
}

async function applyFilters() {
    const myId = ++searchId;
    const f = getFilters();

    const hasSearch   = f.search !== '';
    const hasColFilter = f.cols.some(v => v !== '');

    // Fast path: nothing active — just show everything
    if (!hasSearch && !hasColFilter) {
        filteredData = PARSLER_DATA;
        if (sortCol !== null) sortInPlace();
        currentPage = 0;
        renderPage();
        renderPagination();
        showStatus(PARSLER_DATA.length.toLocaleString() + ' findings', false);
        saveFilters();
        return;
    }

    showStatus('Searching… 0%', true);
    await new Promise(r => setTimeout(r, 0)); // flush status to screen

    const mainRe    = makeRe(f.search, 'i');
    const colRes    = f.cols.map(v => makeRe(v, 'i'));
    const lowerSearch = f.search.toLowerCase();
    // Simple text: no regex metacharacters — use fast indexOf path
    const isSimple  = hasSearch && !/[.*+?^${}()|[\]\\]/.test(f.search);

    const CHUNK = 3000;
    const results = [];

    for (let i = 0; i < PARSLER_DATA.length; i += CHUNK) {
        if (searchId !== myId) return; // a newer search started — bail out

        const end = Math.min(i + CHUNK, PARSLER_DATA.length);
        for (let j = i; j < end; j++) {
            const row = PARSLER_DATA[j];

            // ── Main search ──────────────────────────────────────────────
            if (hasSearch) {
                if (isSimple) {
                    if (!SEARCH_INDEX[j].includes(lowerSearch)) continue;
                } else {
                    mainRe.lastIndex = 0;
                    if (!mainRe.test(SEARCH_INDEX[j])) continue;
                }
            }

            // ── Column filters ───────────────────────────────────────────
            let ok = true;
            for (let c = 0; c < colRes.length; c++) {
                if (!colRes[c]) continue;
                colRes[c].lastIndex = 0;
                if (!colRes[c].test(row[c] || '')) { ok = false; break; }
            }
            if (ok) results.push(row);
        }

        // Yield to UI between chunks so the browser stays responsive
        await new Promise(r => setTimeout(r, 0));
        showStatus('Searching… ' + Math.round(end / PARSLER_DATA.length * 100) + '%', true);
    }

    if (searchId !== myId) return;

    filteredData = results;
    if (sortCol !== null) sortInPlace();
    currentPage = 0;
    renderPage();
    renderPagination();
    showStatus(
        results.length.toLocaleString() + ' of ' + PARSLER_DATA.length.toLocaleString() + ' findings',
        false
    );
    saveFilters();
}

function sortInPlace() {
    const sc = sortCol, sd = sortDir;
    filteredData.sort((a, b) => {
        let av = a[sc] || '', bv = b[sc] || '', cmp = 0;
        if (sc === 0) cmp = (SEV_ORDER[av] ?? 99) - (SEV_ORDER[bv] ?? 99);
        else { av = av.toLowerCase(); bv = bv.toLowerCase(); cmp = av < bv ? -1 : av > bv ? 1 : 0; }
        return sd === 'asc' ? cmp : -cmp;
    });
}

function renderPage() {
    const f = getFilters();
    const mainRe = makeRe(f.search, 'g');
    const colRes = f.cols.map(v => makeRe(v, 'g'));
    const slice  = filteredData.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
    let h = '';
    for (const row of slice) {
        h += '<tr class="severity-' + esc(row[0] || '') + '">';
        for (let i = 0; i < PARSLER_KEYS.length; i++) {
            const raw = row[i] || '';
            const res = [mainRe, colRes[i]].filter(Boolean);
            let cell;
            if (!res.length) {
                cell = esc(raw);
            } else {
                const combined = new RegExp(res.map(r => r.source).join('|'), 'gi');
                cell = highlightText(raw, combined);
            }
            h += '<td class="col-' + PARSLER_KEYS[i] + '">' + cell + '</td>';
        }
        h += '</tr>';
    }
    document.querySelector('tbody').innerHTML = h;
}

function renderPagination() {
    const total = filteredData.length;
    const pages = Math.ceil(total / PAGE_SIZE) || 1;
    const start = total ? currentPage * PAGE_SIZE + 1 : 0;
    const end   = Math.min((currentPage + 1) * PAGE_SIZE, total);
    const text  = total
        ? start.toLocaleString() + '–' + end.toLocaleString() + ' shown'
        : 'No results';
    document.querySelectorAll('.page-info').forEach(el => el.textContent = text);
    document.querySelectorAll('.btn-prev').forEach(el => el.disabled = currentPage === 0);
    document.querySelectorAll('.btn-next').forEach(el => el.disabled = currentPage >= pages - 1);
}

function saveFilters() {
    const f = getFilters();
    try {
        localStorage.setItem('parslerFilters', JSON.stringify(
            {search: f.search, cols: f.cols, sortCol, sortDir}
        ));
    } catch(e) {}
}

function loadFilters() {
    try {
        const s = localStorage.getItem('parslerFilters');
        if (!s) return;
        const st = JSON.parse(s);
        if (st.search) document.getElementById('search-input').value = st.search;
        if (st.cols) {
            const inputs = getColInputs();
            st.cols.forEach((v, i) => { if (inputs[i]) inputs[i].value = v; });
        }
        if (st.sortCol !== undefined) sortCol = st.sortCol;
        if (st.sortDir) sortDir = st.sortDir;
    } catch(e) {}
}

function resetFilters() {
    document.getElementById('search-input').value = '';
    getColInputs().forEach(el => el.value = '');
    sortCol = null; sortDir = 'asc';
    applyFilters();
}

function setQuickFilter(col, val) {
    document.getElementById('search-input').value = '';
    getColInputs().forEach(el => el.value = '');
    sortCol = null; sortDir = 'asc';
    if (col !== null) { const inputs = getColInputs(); if (inputs[col]) inputs[col].value = val; }
    applyFilters();
}

function exportData(type) {
    if (type === 'csv') {
        let csv = PARSLER_KEYS.join(',') + '\n';
        filteredData.forEach(row => {
            csv += PARSLER_KEYS.map((_, i) => '"' + (row[i] || '').replace(/"/g, '""') + '"').join(',') + '\n';
        });
        dlBlob(csv, 'text/csv', 'parsler_export.csv');
    } else {
        const arr = filteredData.map(row => Object.fromEntries(PARSLER_KEYS.map((k, i) => [k, row[i] || ''])));
        dlBlob(JSON.stringify(arr, null, 2), 'application/json', 'parsler_export.json');
    }
}

function dlBlob(content, type, name) {
    const a = Object.assign(document.createElement('a'),
        {href: URL.createObjectURL(new Blob([content], {type})), download: name});
    a.click(); URL.revokeObjectURL(a.href);
}

function changePage(delta) {
    const pages = Math.ceil(filteredData.length / PAGE_SIZE) || 1;
    const np = Math.max(0, Math.min(pages - 1, currentPage + delta));
    if (np !== currentPage) { currentPage = np; renderPage(); renderPagination(); }
}

document.addEventListener('DOMContentLoaded', () => {
    // Build the search index once — join + lowercase every row so searches
    // don't have to re-join on every keystroke
    showStatus('Building index…', true);
    SEARCH_INDEX = PARSLER_DATA.map(row => row.join('\t').toLowerCase());

    // Quick filter buttons
    const qfDiv = document.getElementById('quick-filters');
    const hdr = document.createElement('div');
    hdr.className = 'quick-filters-header'; hdr.textContent = 'Quick Filters';
    qfDiv.appendChild(hdr);
    QUICK_FILTERS.forEach(({name, col, val}) => {
        const btn = document.createElement('button');
        btn.className = 'qf-btn'; btn.textContent = name;
        btn.addEventListener('click', () => col === null ? resetFilters() : setQuickFilter(col, val));
        qfDiv.appendChild(btn);
    });

    // Export buttons
    const expDiv = document.getElementById('export-buttons');
    ['CSV', 'JSON'].forEach(t => {
        const btn = document.createElement('button');
        btn.textContent = 'Export ' + t;
        btn.addEventListener('click', () => exportData(t.toLowerCase()));
        expDiv.appendChild(btn);
    });
    const note = document.createElement('div');
    note.className = 'export-note';
    note.textContent = 'Exports all filtered rows, not just this page.';
    expDiv.appendChild(note);

    // Column header sorting
    document.querySelectorAll('thead th').forEach((th, i) => {
        th.classList.add('sortable');
        th.addEventListener('click', () => {
            sortDir = (sortCol === i && sortDir === 'asc') ? 'desc' : 'asc';
            sortCol = i;
            applyFilters();
        });
    });

    document.getElementById('search-input').addEventListener('input', scheduleFilter);
    getColInputs().forEach(el => el.addEventListener('input', scheduleFilter));
    document.querySelectorAll('.btn-prev').forEach(el => el.addEventListener('click', () => changePage(-1)));
    document.querySelectorAll('.btn-next').forEach(el => el.addEventListener('click', () => changePage(1)));

    loadFilters();
    applyFilters();
});
"""

    css = """
body{background-color:#2e2e2e;color:#e0e0e0;font-family:Arial,sans-serif;padding:20px;font-size:14px;}
.nav-tabs{overflow:hidden;background-color:#1e1e1e;margin-bottom:20px;border-radius:5px;}
.nav-tabs a{float:left;display:block;color:#e0e0e0;text-align:center;padding:10px 14px;text-decoration:none;transition:background-color 0.3s;border-right:1px solid #555;font-size:14px;}
.nav-tabs a:last-child{border-right:none;}
.nav-tabs a:hover,.nav-tabs a.active{background-color:#555;}
h1{margin-top:0;}
.table-wrapper{margin-top:10px;overflow-x:auto;}
table{width:100%;border-collapse:collapse;background-color:#1e1e1e;border:1px solid #444;table-layout:fixed;}
th,td{padding:4px 6px;border:1px solid #444;text-align:left;word-wrap:break-word;font-size:12px;}
.col-severity{width:8%;}.col-rule{width:12%;}.col-keyword{width:10%;}.col-modified{width:10%;}
.col-extension{width:5%;}.col-unc{width:25%;}.col-content{width:30%;}
#search-input{width:100%;padding:10px;margin:10px 0 6px 0;background-color:#444;color:#fff;border:1px solid #555;border-radius:4px;box-sizing:border-box;}
#search-input::placeholder{color:#ccc;}
.filter-row input,.filter-row select{width:100%;padding:6px;margin:4px 0;background-color:#444;color:#fff;border:1px solid #555;border-radius:4px;box-sizing:border-box;}
.filter-row input::placeholder{color:#ccc;}
mark{background-color:yellow;color:#000;font-weight:bold;}
tr.severity-Black:nth-child(even){background-color:#3d3d3d;color:#fff;}
tr.severity-Black:nth-child(odd){background-color:#292929;color:#fff;}
tr.severity-Red:nth-child(even){background-color:#ff5f57;color:#fff;}
tr.severity-Red:nth-child(odd){background-color:#e92929;color:#fff;}
tr.severity-Yellow:nth-child(even){background-color:#ffd760;color:#000;}
tr.severity-Yellow:nth-child(odd){background-color:#ffcd00;color:#000;}
tr.severity-Green:nth-child(even){background-color:#99e699;color:#000;}
tr.severity-Green:nth-child(odd){background-color:#b3ffb3;color:#000;}
tr:hover{background-color:#444!important;color:#fff!important;}
.quick-filters{margin-bottom:10px;}
.quick-filters-header{font-size:16px;margin-bottom:8px;color:#ffd760;}
.qf-btn{margin-right:8px;margin-bottom:8px;padding:5px 10px;background-color:#444;color:#fff;border:1px solid #555;border-radius:4px;cursor:pointer;font-size:14px;}
.qf-btn:hover{background-color:#555;}
.export-buttons{margin-bottom:10px;}
.export-buttons button{margin-right:10px;padding:6px 12px;background-color:#444;color:#fff;border:1px solid #555;border-radius:4px;cursor:pointer;font-size:14px;}
.export-buttons button:hover{background-color:#555;}
.export-note{font-size:12px;color:#ddd;margin-top:6px;}
.sortable:hover{cursor:pointer;text-decoration:underline;}
.pagination{display:flex;align-items:center;gap:12px;margin:8px 0;}
.pagination button{padding:5px 14px;background-color:#444;color:#fff;border:1px solid #555;border-radius:4px;cursor:pointer;font-size:14px;}
.pagination button:hover:not(:disabled){background-color:#555;}
.pagination button:disabled{opacity:0.35;cursor:default;}
.page-info{color:#e0e0e0;font-size:13px;}
#search-status{font-size:13px;min-height:18px;margin:2px 0 8px 0;color:#aaa;letter-spacing:0.02em;}
#search-status.busy{color:#ffd760;animation:status-pulse 1.2s ease-in-out infinite;}
@keyframes status-pulse{0%,100%{opacity:1;}50%{opacity:0.45;}}
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Parsler</title>
<style>{css}</style>
<script src="data.js"></script>
<script>{js}</script>
</head>
<body>
<div class="nav-tabs">
    <a href="full.html" class="active">Main Report</a>
    <a href="tree.html">Tree View</a>
    <a href="stats.html">Stats</a>
    <a href="help.html">Help</a>
</div>
<h1>Parsler - Main Report</h1>
<div id="quick-filters" class="quick-filters"></div>
<label for="search-input"><strong>Search:</strong></label>
<input type="text" id="search-input" placeholder="Regex or plain text search across all columns..." />
<div id="search-status"></div>
<div id="export-buttons" class="export-buttons"></div>
<div class="pagination">
    <button class="btn-prev">&#8592; Prev</button>
    <span class="page-info"></span>
    <button class="btn-next">Next &#8594;</button>
</div>
<div class="table-wrapper">
<table>
<thead>
<tr>
    <th class="col-severity">Severity</th>
    <th class="col-rule">Rule</th>
    <th class="col-keyword">Keyword</th>
    <th class="col-modified">Modified</th>
    <th class="col-extension">Ext</th>
    <th class="col-unc">UNC Path</th>
    <th class="col-content">Content</th>
</tr>
<tr class="filter-row">
    <td class="col-severity">
        <select>
            <option value="">All</option>
            <option value="Black">Black</option>
            <option value="Red">Red</option>
            <option value="Yellow">Yellow</option>
            <option value="Green">Green</option>
        </select>
    </td>
    <td class="col-rule"><input type="text" placeholder="Regex..." /></td>
    <td class="col-keyword"><input type="text" placeholder="Regex..." /></td>
    <td class="col-modified"><input type="text" placeholder="Regex..." /></td>
    <td class="col-extension"><input type="text" placeholder="Regex..." /></td>
    <td class="col-unc"><input type="text" placeholder="Regex..." /></td>
    <td class="col-content"><input type="text" placeholder="Regex..." /></td>
</tr>
</thead>
<tbody></tbody>
</table>
</div>
<div class="pagination" style="margin-top:10px;">
    <button class="btn-prev">&#8592; Prev</button>
    <span class="page-info"></span>
    <button class="btn-next">Next &#8594;</button>
</div>
</body>
</html>"""

    filename = os.path.join(out_dir, "full.html")
    print(f"Saving: {filename}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)



def main():
    parser = argparse.ArgumentParser(description='Parsler - Generate html pages to review Snaffler findings')
    parser.add_argument('-l', '--log', required=True, help='Snaffler log input (tsv format)')
    parser.add_argument('-out', '--out-dir', default='parsler_report', help='Output directory for generated files (Default: parsler_report)')
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)



    if not os.path.isfile(args.log):
        print(f"Input file not found: {args.log}")
        sys.exit(1)
    else:
        print(f"Input file exists: {args.log}")
        input_lines = sum(1 for _ in open(args.log, encoding='utf-8', errors='ignore'))
        if input_lines >= 1:
            with open(args.log, 'r', encoding='utf-8', errors='ignore') as csvfile:
                data_reader = csv.DictReader(csvfile, delimiter='\t', fieldnames=['user', 'timestamp', 'typ', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11'])
                data = list(data_reader)
            outputname = os.path.splitext(os.path.basename(args.log))[0]
            baseInfo = {
                'Snaffler_File': os.path.basename(args.log),
                'SHA256': hashlib.sha256(open(args.log, 'rb').read()).hexdigest()
            }
            with open(args.log, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
            pattern = r'\[(?P<machine>.*?)\\(?P<user>.*?)@.*?\]\s+(?P<timestamp>\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}Z)'
            match = re.match(pattern, first_line)
            if match:
                baseInfo['Snaffler_StartTime'] = match.group('timestamp')
        else:
            print("Input file seems to be empty")
            sys.exit(1)

    shares = []
    for line in data:
        if line['typ'] == '[Share]':
            shares.append({'unc': html.escape(line['2'])})
    shares = list({share['unc']: share for share in shares}.values())

    shares_count = len(shares)
    print(f"Unique shares identified: {shares_count}" if shares_count else "Shares identified: 0")

    files = []
    for line in data:
        if line['typ'] == '[File]' and line['9'] != '':
            severity   = html.escape(line['1'])
            rule       = html.escape(line['2'])
            keyword    = html.escape(line['6'])
            modified   = html.escape(line['8'])
            unc_path   = html.escape(line['9'])
            extension  = html.escape(os.path.splitext(line['9'])[1])
            content    = html.escape(line['11'] or line['10'] or "")

            file_entry = {
                'severity': severity,
                'rule': rule,
                'keyword': keyword,
                'modified': modified,
                'unc': unc_path,
                'extension': extension,
                'content': content
            }
            files.append(file_entry)

    severity_levels = ['Black', 'Red', 'Yellow', 'Green']
    files_by_severity = {sev: [] for sev in severity_levels}

    for fe in files:
        if fe['severity'] in files_by_severity:
            files_by_severity[fe['severity']].append(fe)
        else:
            files_by_severity.setdefault('Unknown', []).append(fe)

    fulloutput = []
    for sev in severity_levels:
        fulloutput.extend(files_by_severity[sev])

    filesum = len(files)
    if filesum < 1:
        print("No [File] entries found.")
        sys.exit(1)
    print(f"Total Snaffler findings: {filesum}")

    modified_date_ranges = {'Last 30 Days': 0, 'Last 6 Months': 0, 'Older Than 1 Year': 0}
    findings_by_severity = {sev: len(files_by_severity[sev]) for sev in severity_levels}
    rule_counts = defaultdict(int)
    host_counts = defaultdict(int)
    extension_counts = defaultdict(int)
    files_by_month = defaultdict(int)
    share_counts = defaultdict(int)

    current_date = datetime.datetime.now()

    for obj in fulloutput:
        # Lowercase host name to unify
        # Also only count the share ignoring case
        if obj['unc']:
            unc_parts = obj['unc'].split('\\')
            if len(unc_parts) > 2:
                # unify host ignoring case
                host_lower = unc_parts[2].lower() or 'unknown'
                host_counts[host_lower] += 1
            if len(unc_parts) > 3:
                # unify share ignoring case
                share_full_lower = f"\\\\{unc_parts[2].lower()}\\{unc_parts[3].lower()}"
                share_counts[share_full_lower] += 1

        if obj['severity']:
            rule_counts[obj['rule']] += 1  # rule counting remains unchanged

        if obj['extension']:
            extension_counts[obj['extension']] += 1

        if obj['modified']:
            try:
                raw_modified = html.unescape(obj['modified'])
                mod_dt = datetime.datetime.strptime(raw_modified, '%Y-%m-%d %H:%M:%SZ')
                delta = current_date - mod_dt
                if delta.days <= 30:
                    modified_date_ranges['Last 30 Days'] += 1
                elif delta.days <= 180:
                    modified_date_ranges['Last 6 Months'] += 1
                else:
                    modified_date_ranges['Older Than 1 Year'] += 1

                month_year = f"{mod_dt.year}-{mod_dt.month:02d}"
                files_by_month[month_year] += 1
            except ValueError:
                pass

    top_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    all_rules_sorted = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)
    top_hosts = sorted(host_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_extensions = sorted(extension_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    stats_dict = {
        'findings_by_severity': findings_by_severity,
        'modified_date_ranges': modified_date_ranges
    }

    def _build_and_write_tree(objects, out_dir):
        tree_root_nodes = build_tree(objects)
        jstree_data = build_jstree(tree_root_nodes)
        generate_tree_html(jstree_data, outputname, out_dir)

    _build_and_write_tree(fulloutput, args.out_dir)
    export_data_js(fulloutput, args.out_dir)
    export_full_html(args.out_dir)
    export_stats_html(
        stats_dict, 
        top_rules,
        top_hosts,
        all_rules_sorted,
        share_counts,
        top_extensions,
        files_by_month,
        outputname,
        args.out_dir
    )
    export_help_html(args.out_dir)

if __name__ == '__main__':
    main()
