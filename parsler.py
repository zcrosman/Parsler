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
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                $('#jstree').jstree({{
                    'core': {{
                        'data': {json.dumps(jstree_data)},
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
                data_reader = csv.DictReader(csvfile, delimiter='\t', fieldnames=['user', 'timestamp', 'typ', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'])
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
            content    = html.escape(line['10'] or "")

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

    def export_html(objects, name, out_dir):
        tree_root_nodes = build_tree(objects)
        jstree_data = build_jstree(tree_root_nodes)
        generate_tree_html(jstree_data, outputname, out_dir)

        filename = os.path.join(out_dir, "full.html")
        print(f"Saving: {filename}")

        keys = ['severity', 'rule', 'keyword', 'modified', 'extension', 'unc', 'content']

        tree_page = "tree.html"
        stats_page = "stats.html"
        help_page = "help.html"

        # The main "full.html" with filters, sorting, searching, exporting
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <title>Parsler</title>
        <style>
        body {{
            background-color: #2e2e2e;
            color: #e0e0e0;
            font-family: Arial, sans-serif;
            padding: 20px;
            font-size: 14px;
        }}
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
        h1 {{
            margin-top: 0;
        }}
        .table-wrapper {{
            margin-top: 20px;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #1e1e1e;
            border: 1px solid #444;
            table-layout: fixed;
        }}
        th, td {{
            padding: 4px 6px;
            border: 1px solid #444;
            text-align: left;
            word-wrap: break-word;
            font-size: 12px;
        }}
        .col-severity {{ width: 8%; }}
        .col-rule {{ width: 12%; }}
        .col-keyword {{ width: 10%; }}
        .col-modified {{ width: 10%; }}
        .col-extension {{ width: 5%; }}
        .col-unc {{ width: 25%; }}
        .col-content {{ width: 30%; }}
        #search-input {{
            width: 100%;
            padding: 10px;
            margin: 10px 0 20px 0;
            background-color: #444;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        #search-input::placeholder {{
            color: #cccccc;
        }}
        .filter-row input, .filter-row select {{
            width: 100%;
            padding: 6px;
            margin: 4px 0;
            background-color: #444;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        .filter-row input::placeholder {{
            color: #cccccc;
        }}
        mark, .highlight {{
            background-color: yellow !important;
            color: #000 !important;
            font-weight: bold !important;
        }}
        tr.severity-Black:nth-child(even) {{
            background-color: #3d3d3d;
            color: #ffffff;
        }}
        tr.severity-Black:nth-child(odd) {{
            background-color: #292929;
            color: #ffffff;
        }}
        tr.severity-Red:nth-child(even) {{
            background-color: #ff5f57;
            color: #ffffff;
        }}
        tr.severity-Red:nth-child(odd) {{
            background-color: #e92929;
            color: #ffffff;
        }}
        tr.severity-Yellow:nth-child(even) {{
            background-color: #ffd760;
            color: #000000;
        }}
        tr.severity-Yellow:nth-child(odd) {{
            background-color: #ffcd00;
            color: #000000;
        }}
        tr.severity-Green:nth-child(even) {{
            background-color: #99e699;
            color: #000000;
        }}
        tr.severity-Green:nth-child(odd) {{
            background-color: #b3ffb3;
            color: #000000;
        }}
        tr:hover {{
            background-color: #444;
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
        .export-buttons {{
            margin-bottom: 10px;
        }}
        .export-buttons button {{
            margin-right: 10px;
            padding: 6px 12px;
            background-color: #444;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 4px;
            cursor: pointer;
            font-size:14px;
        }}
        .export-buttons button:hover {{
            background-color: #555;
        }}
        .export-note {{
            font-size: 12px;
            color: #ddd;
            margin-bottom: 10px;
            margin-top: 10px;
        }}
        .sortable:hover {{
            cursor: pointer;
            text-decoration: underline;
        }}
        </style>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            let sortColumnIndex = null;
            let sortDirection = 'asc';

            function loadFilters() {{
                const saved = localStorage.getItem('filterState');
                if (!saved) return;
                const state = JSON.parse(saved);
                if (state.searchValue) document.querySelector('#search-input').value = state.searchValue;
                const filterCells = document.querySelectorAll('.filter-row input, .filter-row select');
                filterCells.forEach((filter, index) => {{
                    const key = 'filter_' + index;
                    if (state[key] !== undefined) {{
                        filter.value = state[key];
                    }}
                }});
                if (state.sortColumnIndex !== undefined) {{
                    sortColumnIndex = state.sortColumnIndex;
                    sortDirection = state.sortDirection;
                }}
            }}

            function saveFilters() {{
                const state = {{}};
                state.searchValue = document.querySelector('#search-input').value;
                const filterCells = document.querySelectorAll('.filter-row input, .filter-row select');
                filterCells.forEach((filter, index) => {{
                    const key = 'filter_' + index;
                    state[key] = filter.value;
                }});
                state.sortColumnIndex = sortColumnIndex;
                state.sortDirection = sortDirection;
                localStorage.setItem('filterState', JSON.stringify(state));
            }}

            function resetFilters() {{
                document.querySelectorAll('.filter-row input').forEach(input => {{
                    input.value = '';
                }});
                document.querySelectorAll('.filter-row select').forEach(select => {{
                    select.value = '';
                }});
                document.querySelector('#search-input').value = '';
                sortColumnIndex = null;
                sortDirection = 'asc';
                saveFilters();
                filterTable();
            }}

            function filterTable() {{
                const filters = Array.from(document.querySelectorAll('.filter-row input, .filter-row select'));
                const rows = Array.from(document.querySelectorAll('tbody tr'));
                const searchValue = document.querySelector('#search-input').value.trim();

                let mainRegex = null;
                if (searchValue) {{
                    try {{
                        mainRegex = new RegExp(searchValue, 'gi');
                    }} catch(e) {{
                        console.error('Invalid main search regex:', searchValue);
                    }}
                }}

                const colRegexes = [];
                filters.forEach((filter, index) => {{
                    const val = filter.value.trim();
                    if (val !== '') {{
                        try {{
                            colRegexes[index] = new RegExp(val, 'i');
                        }} catch(e) {{
                            console.error('Invalid column filter regex:', val);
                            colRegexes[index] = null;
                        }}
                    }} else {{
                        colRegexes[index] = null;
                    }}
                }});

                rows.forEach(row => {{
                    const cells = row.querySelectorAll('td');

                    // Restore un-highlighted text
                    cells.forEach(cell => {{
                        if (cell.dataset.origText) {{
                            cell.innerHTML = cell.dataset.origText;
                        }} else {{
                            cell.dataset.origText = cell.innerHTML;
                        }}
                    }});

                    let matchesSearch = true;
                    if (mainRegex) {{
                        matchesSearch = mainRegex.test(row.textContent);
                        mainRegex.lastIndex = 0;
                    }}

                    let matchesFilters = true;
                    filters.forEach((filter, colIndex) => {{
                        const val = filter.value.trim();
                        if (!val) return;
                        if (!colRegexes[colIndex]) return;

                        const cellText = cells[colIndex].textContent;
                        if (!colRegexes[colIndex].test(cellText)) {{
                            matchesFilters = false;
                        }}
                        colRegexes[colIndex].lastIndex = 0;
                    }});

                    if (matchesSearch && matchesFilters) {{
                        row.style.display = '';
                        // Highlight matches (both master search & column filters)
                        cells.forEach((cell, colIndex) => {{
                            let orig = cell.innerHTML;
                            // Master search highlight
                            if (mainRegex) {{
                                orig = orig.replace(mainRegex, match => '<span class="highlight">' + match + '</span>');
                                mainRegex.lastIndex = 0;
                            }}
                            // Column filter highlight
                            if (colRegexes[colIndex]) {{
                                orig = orig.replace(colRegexes[colIndex], match => '<span class="highlight">' + match + '</span>');
                                colRegexes[colIndex].lastIndex = 0;
                            }}
                            cell.innerHTML = orig;
                        }});
                    }} else {{
                        row.style.display = 'none';
                    }}
                }});

                if (sortColumnIndex !== null) {{
                    sortRows(rows);
                }}

                saveFilters();
            }}

            function sortRows(rows) {{
                const tbody = document.querySelector('tbody');
                const visibleRows = rows.filter(r => r.style.display !== 'none');
                visibleRows.sort((a,b) => {{
                    const aCell = a.children[sortColumnIndex].textContent.trim();
                    const bCell = b.children[sortColumnIndex].textContent.trim();
                    let cmp = 0;
                    if (sortColumnIndex === 0) {{
                        const severityOrder = {{'Black':1, 'Red':2, 'Yellow':3, 'Green':4}};
                        cmp = (severityOrder[aCell] || 99) - (severityOrder[bCell] || 99);
                    }} else {{
                        const aLower = aCell.toLowerCase();
                        const bLower = bCell.toLowerCase();
                        if (aLower < bLower) cmp = -1;
                        else if (aLower > bLower) cmp = 1;
                    }}
                    return sortDirection === 'asc' ? cmp : -cmp;
                }});
                visibleRows.forEach(r => tbody.appendChild(r));
            }}

            function initColumnSorting() {{
                const headers = document.querySelectorAll('thead th');
                headers.forEach((th, i) => {{
                    th.classList.add('sortable');
                    th.addEventListener('click', () => {{
                        if (sortColumnIndex === i) {{
                            sortDirection = (sortDirection === 'asc') ? 'desc' : 'asc';
                        }} else {{
                            sortColumnIndex = i;
                            sortDirection = 'asc';
                        }}
                        filterTable();
                    }});
                }});
            }}

            function exportFilteredData(type) {{
                const rows = Array.from(document.querySelectorAll('tbody tr')).filter(r => r.style.display !== 'none');
                const headers = Array.from(document.querySelectorAll('thead th'));
                const colKeys = headers.map(h => h.textContent.toLowerCase());

                if (type === 'csv') {{
                    let csvContent = colKeys.join(',') + '\\n';
                    rows.forEach(r => {{
                        const cells = Array.from(r.children).map(c => c.textContent.replace(/"/g,'""'));
                        csvContent += '"' + cells.join('","') + '"\\n';
                    }});
                    const blob = new Blob([csvContent], {{type: 'text/csv'}});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'filtered_data.csv';
                    a.click();
                    URL.revokeObjectURL(url);
                }} else if (type === 'json') {{
                    const jsonArray = rows.map(r => {{
                        const obj = {{}};
                        colKeys.forEach((k, idx) => {{
                            obj[k] = r.children[idx].textContent;
                        }});
                        return obj;
                    }});
                    const blob = new Blob([JSON.stringify(jsonArray, null, 2)], {{type: 'application/json'}});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'filtered_data.json';
                    a.click();
                    URL.revokeObjectURL(url);
                }}
            }}

            const quickFilters = {{
                'Office Docs': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(doc|xls|ppt)$';
                    filterTable();
                }},
                'Connection Strings': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-keyword input').value = 'connectionstring';
                    filterTable();
                }},
                'Password Filenames': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-rule input').value = 'password';
                    filterTable();
                }},
                'SA Account': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-content input').value = '\\\\\\\\?[\\\"\\\']?sa\\\\\\\\?[\\\"\\\']';
                    filterTable();
                }},
                'Connection String PW': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-content input').value = ';Password=';
                    filterTable();
                }},
                'Configuration Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(config|conf|cfg|ini|xml|json|yaml|yml)$';
                    filterTable();
                }},
                'Log Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(log|txt)$';
                    filterTable();
                }},
                'Backup Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(bak|backup|old|tmp)$';
                    filterTable();
                }},
                'Executable Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(exe|dll|bat|sh|ps1|bin)$';
                    filterTable();
                }},
                'Database Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(db|sqlite|sql|mdf|sdf|dat|accdb)$';
                    filterTable();
                }},
                'Email Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(pst|ost|eml|msg)$';
                    filterTable();
                }},
                'Certificate Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(pem|crt|cer|pfx|p12|key)$';
                    filterTable();
                }},
                'Source Code Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(py|js|java|c|cpp|ts|rb|go|php|sh|bat)$';
                    filterTable();
                }},
                'Key Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(pem|ppk|key|ssh)$';
                    filterTable();
                }},
                'Financial Data': () => {{
                    resetFilters();
                    // document.querySelector('.filter-row .col-extension input').value = '\\\\.(xls|xlsx|csv)$';
                    document.querySelector('.filter-row .col-unc input').value = 'financial|invoice|receipt';
                    filterTable();
                }},
                'Personal Data': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-content input').value = '(ssn|social security|dob|birthdate)';
                    filterTable();
                }},
                'Encryption Keys': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-content input').value = 'AES|RSA|PGP';
                    filterTable();
                }},
                'Private Keys': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-content input').value = 'PRIVATE KEY';
                    filterTable();
                }},
                'Health Records': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-content input').value = '(hipaa|medical|patient)';
                    filterTable();
                }},
                'Executable or Scripts': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(exe|dll|sh|bat|ps1|vbs|cmd|pl)$';
                    filterTable();
                }},
                'Archived Files': () => {{
                    resetFilters();
                    document.querySelector('.filter-row .col-extension input').value = '\\\\.(zip|tar|gz|7z|rar|iso)$';
                    filterTable();
                }},
                'Reset Filters': () => {{
                    resetFilters();
                    filterTable();
                }}
            }};

            function createExportButtons() {{
                const container = document.createElement('div');
                container.className = 'export-buttons';
                const csvBtn = document.createElement('button');
                csvBtn.textContent = 'Export CSV';
                csvBtn.addEventListener('click', () => exportFilteredData('csv'));
                container.appendChild(csvBtn);

                const jsonBtn = document.createElement('button');
                jsonBtn.textContent = 'Export JSON';
                jsonBtn.addEventListener('click', () => exportFilteredData('json'));
                container.appendChild(jsonBtn);

                const note = document.createElement('div');
                note.className = 'export-note';
                note.textContent = 'Note: Export only includes currently visible (filtered) rows.';
                container.appendChild(note);

                const quickFiltersDiv = document.querySelector('.quick-filters');
                quickFiltersDiv.parentNode.insertBefore(container, quickFiltersDiv);
            }}

            function createQuickFiltersHeaderAndButtons() {{
                const quickFilterContainer = document.querySelector('.quick-filters');
                const quickFiltersHeader = document.createElement('div');
                quickFiltersHeader.className = 'quick-filters-header';
                quickFiltersHeader.textContent = 'Quick Filters (WIP)';
                quickFilterContainer.appendChild(quickFiltersHeader);

                Object.keys(quickFilters).forEach(filterName => {{
                    const button = document.createElement('button');
                    button.textContent = filterName;
                    button.addEventListener('click', quickFilters[filterName]);
                    button.className = 'qf-btn';
                    quickFilterContainer.appendChild(button);
                }});
            }}

            function setActiveTab(currentPage) {{
                const tabs = document.querySelectorAll('.nav-tabs a');
                tabs.forEach(tab => {{
                    if (tab.textContent === currentPage) {{
                        tab.classList.add('active');
                    }} else {{
                        tab.classList.remove('active');
                    }}
                }});
            }}

            loadFilters();
            initColumnSorting();
            filterTable();
            document.querySelector('#search-input').addEventListener('input', filterTable);
            document.querySelectorAll('.filter-row input, .filter-row select').forEach(f => {{
                f.addEventListener('input', filterTable);
            }});
            createExportButtons();
            createQuickFiltersHeaderAndButtons();
            setActiveTab('Main Report');
        }});
        </script>
        </head>
        <body>
            <div class="nav-tabs">
                <a href="full.html" class="tab-link active">Main Report</a>
                <a href="{tree_page}" class="tab-link">Tree View</a>
                <a href="{stats_page}" class="tab-link">Stats</a>
                <a href="{help_page}" class="tab-link">Help</a>
            </div>

            <h1>Parsler - Main Report</h1>

            <div class="quick-filters"></div>
            <label for="search-input"><strong>Search:</strong></label>
            <input type="text" id="search-input" placeholder="Regex search across all columns..." />
            <div class="export-buttons"></div>

            <div class="table-wrapper">
            <table>
            <thead>
            <tr>
        """

        # Table headers
        for k in keys:
            html_template += f"<th class='col-{k}'>{k.capitalize()}</th>"
        html_template += """
            </tr>
            <tr class="filter-row">
        """
        # Column filter row
        for k in keys:
            if k == 'severity':
                html_template += """
                <td class='col-severity'>
                    <select>
                        <option value="">All</option>
                        <option value="Black">Black</option>
                        <option value="Red">Red</option>
                        <option value="Yellow">Yellow</option>
                        <option value="Green">Green</option>
                    </select>
                </td>
                """
            else:
                html_template += f"<td class='col-{k}'><input type='text' placeholder='Regex filter...' /></td>"
        html_template += """
            </tr>
            </thead>
            <tbody>
        """

        for obj in objects:
            severity_class = f"severity-{html.unescape(obj.get('severity', ''))}"
            html_template += f"<tr class='{severity_class}'>"
            for k in keys:
                val = obj.get(k, '')
                html_template += f"<td class='col-{k}'>{val}</td>"
            html_template += "</tr>\n"

        html_template += f"""
            </tbody>
            </table>
            </div>
            <p>
                <a href="{tree_page}">View as Tree</a> | 
                <a href="{stats_page}">View Stats</a> | 
                <a href="{help_page}">Help</a>
            </p>
        </body>
        </html>
        """

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_template)

    export_html(fulloutput, 'full', args.out_dir)
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
