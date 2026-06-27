#!/usr/bin/env python3
"""uasset MCP 批量对比脚本"""
import http.client
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ENDPOINT = 'http://127.0.0.1:8000/mcp'
SAMPLES_ROOT = Path(r'E:\Develop\lib\Samples')
OUTPUT_DIR = Path(r'E:\Develop\uasset_read\temp')

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.uasset_read import parse_uasset


class McpClient:
    def __init__(self):
        self.session_id = None
        self._next_id = 0

    def _call(self, method, params=None):
        url = urlsplit(ENDPOINT)
        self._next_id += 1
        payload = json.dumps({'jsonrpc': '2.0', 'id': self._next_id, 'method': method, 'params': params or {}})
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if self.session_id:
            headers['Mcp-Session-Id'] = self.session_id
        conn = http.client.HTTPConnection(url.hostname, url.port, timeout=60)
        conn.request('POST', url.path or '/mcp', payload, headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        if not self.session_id:
            self.session_id = resp.getheader('Mcp-Session-Id')
        if body.strip().startswith('event:'):
            data_lines = [line[5:].lstrip() for line in body.splitlines() if line.startswith('data:')]
            body = '\n'.join(data_lines)
        if not body:
            return None
        data = json.loads(body)
        if 'result' in data:
            content = data['result'].get('content', [])
            if content:
                text = content[0].get('text', '{}')
                try:
                    return json.loads(text)
                except:
                    return text
        return data

    def connect(self):
        self._call('initialize', {
            'protocolVersion': '2025-03-26',
            'capabilities': {},
            'clientInfo': {'name': 'compare', 'version': '1.0'}
        })
        self._call('notifications/initialized', {})
        return True

    def call_tool(self, toolset, tool, args):
        return self._call('tools/call', {
            'name': 'call_tool',
            'arguments': {'toolset_name': toolset, 'tool_name': tool, 'arguments': args}
        })


def get_ue_ref_path(file_path, content_root):
    rel = file_path.relative_to(content_root)
    parts = rel.parts[:-1]
    name = file_path.stem
    return '/Game/' + '/'.join(parts) + '/' + name + '.' + name


def parse_bp(file_path):
    try:
        result = parse_uasset(str(file_path))
        graphs = [g.graph_name for g in result.graphs if hasattr(g, 'graph_name')]
        export_count = result.summary.export_count if result.summary else 0
        return {'success': True, 'graphs': graphs, 'export_count': export_count}
    except Exception as e:
        return {'success': False, 'error': str(e), 'graphs': [], 'export_count': 0}


def compare_project(project_name, bp_files, client):
    print(f'\n{"="*60}')
    print(f'项目: {project_name}')
    print(f'{"="*60}')

    content_root = SAMPLES_ROOT / project_name / 'Content'
    comparisons = []

    for bp_file in bp_files[:10]:
        bp_name = bp_file.name
        ref_path = get_ue_ref_path(bp_file, content_root)

        print(f'\n{bp_name}')
        parse_result = parse_bp(bp_file)
        if not parse_result['success']:
            print(f'  解析失败: {parse_result["error"][:50]}')
            continue

        print(f'  解析图: {len(parse_result["graphs"])}')

        graphs_resp = client.call_tool(
            'editor_toolset.toolsets.blueprint.BlueprintTools',
            'list_graphs',
            {'blueprint': {'refPath': ref_path}}
        )

        mcp_graphs = []
        if graphs_resp and isinstance(graphs_resp, dict) and 'returnValue' in graphs_resp:
            mcp_graphs = [item['refPath'].split(':')[-1] for item in graphs_resp['returnValue']]
        print(f'  MCP图: {len(mcp_graphs)}')

        parse_set = set(parse_result['graphs'])
        mcp_set = set(mcp_graphs)
        matched = len(parse_set & mcp_set)
        match_rate = f'{matched/len(mcp_set)*100:.1f}%' if mcp_set else 'N/A'
        print(f'  匹配: {matched}/{len(mcp_set)} ({match_rate})')

        comparisons.append({
            'file': bp_name,
            'export_count': parse_result['export_count'],
            'parse_graphs': parse_result['graphs'],
            'mcp_graphs': mcp_graphs,
            'matched': matched,
            'total_mcp': len(mcp_set)
        })
        time.sleep(0.3)

    total_mcp = sum(c['total_mcp'] for c in comparisons)
    total_matched = sum(c['matched'] for c in comparisons)
    overall_rate = f'{total_matched/total_mcp*100:.1f}%' if total_mcp > 0 else 'N/A'

    print(f'\n{"-"*40}')
    print(f'{project_name} 总结: {total_matched}/{total_mcp} ({overall_rate})')

    return {
        'project': project_name,
        'comparisons': comparisons,
        'summary': {'total_mcp': total_mcp, 'matched': total_matched, 'match_rate': overall_rate}
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='uasset MCP 批量对比')
    parser.add_argument('--projects', required=True, help='项目名称（逗号分隔）')
    parser.add_argument('--output', help='输出文件路径')
    args = parser.parse_args()

    projects = args.projects.split(',')

    client = McpClient()
    client.connect()
    print('MCP 连接成功\n')

    all_results = []
    for proj_name in projects:
        proj_path = SAMPLES_ROOT / proj_name
        if not proj_path.exists():
            print(f'跳过不存在的项目: {proj_name}')
            continue

        bp_files = list(proj_path.glob('**/BP_*.uasset'))
        if bp_files:
            result = compare_project(proj_name, bp_files, client)
            all_results.append(result)

    output_file = Path(args.output) if args.output else OUTPUT_DIR / 'batch-mcp-comparison-report.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f'\n{"="*60}')
    print('所有项目总结:')
    print(f'{"="*60}')
    grand_total = sum(r['summary']['total_mcp'] for r in all_results)
    grand_matched = sum(r['summary']['matched'] for r in all_results)
    for r in all_results:
        print(f"  {r['project']}: {r['summary']['matched']}/{r['summary']['total_mcp']} ({r['summary']['match_rate']})")
    print(f"\n总计: {grand_matched}/{grand_total} ({grand_matched/grand_total*100:.1f}%)" if grand_total > 0 else "\n总计: N/A")
    print(f'\n报告: {output_file}')


if __name__ == '__main__':
    main()
