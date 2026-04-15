import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill


def process_singles(df_singles):
    """
    处理单打报名数据
    返回：(记录列表, 重名字典, 重复提交字典)
    """
    df_singles.columns = [str(col).strip() for col in df_singles.columns]

    required_columns = ['序号', '学院部门（教学科研单位、研究机构）', '姓名', '你的性别', '学号']

    # 检查必需的列是否存在
    missing_columns = [col for col in required_columns if col not in df_singles.columns]
    if missing_columns:
        print(f"警告：单打报名表中缺少以下列：{missing_columns}")
        return [], {}, {}

    df_selected = df_singles[required_columns].copy()
    df_selected.columns = ['序号', '学院部门', '姓名', '性别', '学号']

    # 检测重名和重复报名
    name_dict = {}
    for idx, row in df_selected.iterrows():
        name = row['姓名']
        if name not in name_dict:
            name_dict[name] = []
        name_dict[name].append({
            'index': idx,
            '学号': row['学号'],
            '学院部门': row['学院部门'],
            'row_data': row
        })

    duplicate_names = {}
    duplicate_submissions = {}

    for name, records in name_dict.items():
        if len(records) > 1:
            unique_persons = {}
            for record in records:
                key = (record['学号'], record['学院部门'])
                if key not in unique_persons:
                    unique_persons[key] = []
                unique_persons[key].append(record['index'])

            if len(unique_persons) == 1:
                duplicate_submissions[name] = [r['index'] for r in records]
            else:
                duplicate_names[name] = [r['index'] for r in records]

    # 创建输出记录
    output_data = []
    for idx, row in df_selected.iterrows():
        if row['性别'] == '男':
            project = '男子单打'
        elif row['性别'] == '女':
            project = '女子单打'
        else:
            project = '未知'

        record = {
            '队名或单位': row['学院部门'],
            '领队': '',
            '主教练': '',
            '组别': '',
            '项目(必填)': project,
            '种子号': '',
            '队内序号': '',
            '团体名(必填)': row['姓名'],
            '队员(必填)': row['姓名'],
            '团体项目': '',
            '性别(必填)': row['性别'],
            '身份证号': '',
            '手机': '',
            '队员备注': '',
            '附加': '',
            '_source': 'singles',
            '_original_index': idx
        }
        output_data.append(record)

    return output_data, duplicate_names, duplicate_submissions


def infer_partner_gender(player_gender, project_type):
    """
    根据报名人性别和项目类型推断搭档性别
    """
    if project_type == '男子双打':
        return '男'
    elif project_type == '女子双打':
        return '女'
    elif project_type == '混合双打':
        # 混双中，搭档性别与报名人相反
        return '女' if player_gender == '男' else '男'
    return ''


def process_doubles(df_doubles):
    """
    处理双打报名数据（按行读取，每行一份报名）
    返回：(记录列表, 重复组合字典)
    """
    output_data = []
    duplicate_pairs = {}

    df_doubles.columns = [str(col).strip() for col in df_doubles.columns]

    required_columns = ['你的姓名', '你的性别']
    missing_columns = [col for col in required_columns if col not in df_doubles.columns]
    if missing_columns:
        print(f"警告：双打报名表中缺少以下列：{missing_columns}")
        return [], {}

    # 兼容重复列名：报名项目、报名项目.1 等
    project_cols = [col for col in df_doubles.columns if str(col).startswith('报名项目')]
    if not project_cols:
        print("警告：双打报名表中缺少“报名项目”列")
        return [], {}

    # 兼容可能的列名变化
    male_partner_col = None
    mixed_partner_col = None
    female_partner_col = None

    for col in df_doubles.columns:
        col_str = str(col).strip()
        if col_str == '男双队友姓名':
            male_partner_col = col
        elif col_str == '混双队友姓名':
            mixed_partner_col = col
        elif col_str == '女双队友姓名':
            female_partner_col = col

    # 用于追踪每个组合
    pair_tracker = {}  # key: (项目, 人1, 人2), value: [记录起始索引列表]

    for idx, row in df_doubles.iterrows():
        name = str(row['你的姓名']).strip() if pd.notna(row['你的姓名']) else ''
        gender = str(row['你的性别']).strip() if pd.notna(row['你的性别']) else ''

        if not name or name == 'nan' or name == '你的姓名':
            continue

        # 汇总所有“报名项目”列中的非空值
        project_values = []
        for col in project_cols:
            if col in row and pd.notna(row[col]):
                val = str(row[col]).strip()
                if val and val != 'nan' and val not in project_values:
                    project_values.append(val)

        if not project_values:
            continue

        projects_str = '，'.join(project_values)
        projects = [p.strip() for p in projects_str.replace(',', '，').split('，') if p.strip()]

        for project in projects:
            partner_name = None
            project_type = None

            if '男子双打' in project or '男双' in project:
                project_type = '男子双打'
                if male_partner_col and pd.notna(row.get(male_partner_col)):
                    partner_name = str(row.get(male_partner_col)).strip()

            elif '混合双打' in project or '混双' in project:
                project_type = '混合双打'
                if mixed_partner_col and pd.notna(row.get(mixed_partner_col)):
                    partner_name = str(row.get(mixed_partner_col)).strip()

            elif '女子双打' in project or '女双' in project:
                project_type = '女子双打'
                if female_partner_col and pd.notna(row.get(female_partner_col)):
                    partner_name = str(row.get(female_partner_col)).strip()

            else:
                continue

            if not partner_name or partner_name == 'nan':
                continue

            # 根据报名人性别和项目类型推断搭档性别
            partner_gender = infer_partner_gender(gender, project_type)

            # 创建组合标识（按字母顺序排序，确保同一组合有相同的key）
            pair_key = tuple(sorted([name, partner_name]))
            combo_key = (project_type, pair_key[0], pair_key[1])

            if combo_key not in pair_tracker:
                pair_tracker[combo_key] = []

            # 记录这个组合的起始行索引
            start_idx = len(output_data)
            pair_tracker[combo_key].append(start_idx)

            # 创建团体名（保持原始顺序）
            team_name = f"{name}/{partner_name}"

            # 为这对组合创建两行记录
            # 第一行：填写报名人
            record1 = {
                '队名或单位': '',
                '领队': '',
                '主教练': '',
                '组别': '',
                '项目(必填)': project_type,
                '种子号': '',
                '队内序号': '',
                '团体名(必填)': team_name,
                '队员(必填)': name,
                '团体项目': '',
                '性别(必填)': gender,
                '身份证号': '',
                '手机': '',
                '队员备注': '',
                '附加': '',
                '_source': 'doubles',
                '_original_index': idx,
                '_combo_key': combo_key
            }
            output_data.append(record1)

            # 第二行：填写队友
            record2 = {
                '队名或单位': '',
                '领队': '',
                '主教练': '',
                '组别': '',
                '项目(必填)': project_type,
                '种子号': '',
                '队内序号': '',
                '团体名(必填)': team_name,
                '队员(必填)': partner_name,
                '团体项目': '',
                '性别(必填)': partner_gender,
                '身份证号': '',
                '手机': '',
                '队员备注': '',
                '附加': '',
                '_source': 'doubles',
                '_original_index': idx,
                '_combo_key': combo_key
            }
            output_data.append(record2)

    # 找出重复的组合（同一组合有多人填写了）
    for combo_key, indices in pair_tracker.items():
        if len(indices) > 1:
            # 将所有相关的行都标记为重复
            all_rows = []
            for start_idx in indices:
                all_rows.extend([start_idx, start_idx + 1])  # 每个组合有两行
            duplicate_pairs[combo_key] = all_rows

    return output_data, duplicate_pairs


def extract_member_name(member_info):
    """
    从成员字符串中提取姓名
    例如：
    '姓名：张三' -> '张三'
    其他内容 -> ''
    """
    if pd.isna(member_info):
        return ''

    text = str(member_info).strip()
    if not text or text == 'nan':
        return ''

    if '姓名：' in text:
        name = text.split('姓名：', 1)[1].strip()
        if name and name not in ['0', 'nan', 'None']:
            return name

    return ''


def process_team(df_team):
    """
    处理团体报名数据
    返回：记录列表
    """
    output_data = []

    df_team.columns = [str(col).strip() for col in df_team.columns]

    unit_col = '学院部门（教学科研单位、研究机构）'
    if unit_col not in df_team.columns:
        print(f"警告：团体报名表中缺少列：{unit_col}")
        return []

    for idx, row in df_team.iterrows():
        unit = str(row[unit_col]).strip() if pd.notna(row[unit_col]) else ''
        if not unit or unit == 'nan':
            continue

        team_name = unit
        members = []

        # 扫描整行，凡是“姓名：xxx”都提取出来
        for value in row.tolist():
            name = extract_member_name(value)
            if name and name not in members:
                members.append(name)

        if not members:
            continue

        # 为每个队员创建一条记录
        for member in members:
            record = {
                '队名或单位': unit,
                '领队': '',
                '主教练': '',
                '组别': '',
                '项目(必填)': '混合团体',
                '种子号': '',
                '队内序号': '',
                '团体名(必填)': team_name,
                '队员(必填)': member,
                '团体项目': '',
                '性别(必填)': '',
                '身份证号': '',
                '手机': '',
                '队员备注': '',
                '附加': '',
                '_source': 'team',
                '_original_index': idx
            }
            output_data.append(record)

    return output_data


def convert_all_registrations(singles_file, doubles_file, team_file, output_file):
    """
    转换所有报名数据
    """
    all_records = []
    row_colors = {}

    print("\n" + "=" * 60)
    print("开始处理报名数据...")
    print("=" * 60)

    # 处理单打
    if singles_file and os.path.exists(singles_file):
        print("\n正在处理单打报名数据...")
        df_singles = pd.read_excel(singles_file)
        singles_records, dup_names, dup_subs = process_singles(df_singles)

        start_row = len(all_records)
        all_records.extend(singles_records)

        # 标记单打的重名和重复提交
        for name, indices in dup_names.items():
            for idx in indices:
                matching_records = [i for i, r in enumerate(singles_records)
                                    if r['_original_index'] == idx]
                for match_idx in matching_records:
                    row_colors[start_row + match_idx] = 'yellow'

        for name, indices in dup_subs.items():
            for idx in indices:
                matching_records = [i for i, r in enumerate(singles_records)
                                    if r['_original_index'] == idx]
                for match_idx in matching_records:
                    row_colors[start_row + match_idx] = 'red'

        print(f"  ✓ 单打：处理 {len(singles_records)} 条记录")
        if dup_names:
            print(f"  ⚠ 发现 {len(dup_names)} 组重名（已标黄）")
        if dup_subs:
            print(f"  ⚠ 发现 {len(dup_subs)} 人重复提交（已标红）")

    # 处理双打
    if doubles_file and os.path.exists(doubles_file):
        print("\n正在处理双打报名数据...")
        df_doubles = pd.read_excel(doubles_file)
        doubles_records, dup_pairs = process_doubles(df_doubles)

        start_row = len(all_records)
        all_records.extend(doubles_records)

        # 标记重复的组合
        for combo_key, row_indices in dup_pairs.items():
            for idx in row_indices:
                row_colors[start_row + idx] = 'red'

        print(f"  ✓ 双打：处理 {len(doubles_records)} 条记录（{len(doubles_records) // 2} 对组合）")
        if dup_pairs:
            print(f"  ⚠ 发现 {len(dup_pairs)} 组重复组合（已标红）")
            for combo_key, indices in dup_pairs.items():
                project, p1, p2 = combo_key
                print(f"    - {project}: {p1}/{p2} (重复{len(indices) // 2}次)")

    # 处理团体
    if team_file and os.path.exists(team_file):
        print("\n正在处理团体报名数据...")
        df_team = pd.read_excel(team_file)
        team_records = process_team(df_team)
        all_records.extend(team_records)
        print(f"  ✓ 团体：处理 {len(team_records)} 条记录")

    if not all_records:
        print("\n错误：没有有效的报名数据！")
        return False

    # 移除临时字段
    for record in all_records:
        record.pop('_source', None)
        record.pop('_original_index', None)
        record.pop('_combo_key', None)

    # 保存到Excel
    print("\n正在保存文件...")
    df_output = pd.DataFrame(all_records)
    df_output.to_excel(output_file, index=False, engine='openpyxl')

    # 添加颜色标记
    wb = load_workbook(output_file)
    ws = wb.active

    yellow_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')

    for row_num, color in row_colors.items():
        excel_row = row_num + 2  # +2 因为有表头且从1开始
        if color == 'yellow':
            for cell in ws[excel_row]:
                cell.fill = yellow_fill
        elif color == 'red':
            for cell in ws[excel_row]:
                cell.fill = red_fill

    wb.save(output_file)

    print("\n" + "=" * 60)
    print(f"✓ 转换完成！共处理 {len(all_records)} 条记录")
    print(f"✓ 输出文件已保存至: {output_file}")
    print("=" * 60)

    return True


def main():
    """
    主函数：交互式输入文件路径
    """
    print("=" * 60)
    print("乒乓球赛事报名数据转换工具（完整版）")
    print("=" * 60)
    print()

    # 输入单打文件
    print("【1/3】单打报名文件")
    singles_file = input("请输入单打报名文件路径（无则直接回车跳过）：").strip().strip('"').strip("'")
    if singles_file and not os.path.exists(singles_file):
        print(f"警告：文件不存在，将跳过单打数据")
        singles_file = None

    # 输入双打文件
    print("\n【2/3】双打报名文件")
    doubles_file = input("请输入双打报名文件路径（无则直接回车跳过）：").strip().strip('"').strip("'")
    if doubles_file and not os.path.exists(doubles_file):
        print(f"警告：文件不存在，将跳过双打数据")
        doubles_file = None

    # 输入团体文件
    print("\n【3/3】团体报名文件")
    team_file = input("请输入团体报名文件路径（无则直接回车跳过）：").strip().strip('"').strip("'")
    if team_file and not os.path.exists(team_file):
        print(f"警告：文件不存在，将跳过团体数据")
        team_file = None

    if not any([singles_file, doubles_file, team_file]):
        print("\n错误：至少需要提供一个报名文件！")
        input("\n按回车键退出...")
        return

    # 输入输出文件路径
    print("\n【输出文件】")
    default_dir = os.path.dirname(singles_file or doubles_file or team_file)
    default_output = os.path.join(default_dir, "sheet_output.xlsx")
    output_file = input(
        f"请输入输出文件路径（直接回车使用默认路径）\n默认路径: {default_output}\n输入路径："
    ).strip().strip('"').strip("'")

    if not output_file:
        output_file = default_output

    # 执行转换
    try:
        convert_all_registrations(singles_file, doubles_file, team_file, output_file)
        input("\n按回车键退出...")
    except Exception as e:
        print(f"\n转换过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
