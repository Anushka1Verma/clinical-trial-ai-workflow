import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .model import AdaptionPolicy, RulesPolicy


@dataclass(frozen=True)
class Citation:
    file: str
    line: int
    text: str


@dataclass(frozen=True)
class Requirement:
    outcome: str
    measurement: str
    visits: tuple[str, ...]
    source: Citation


@dataclass(frozen=True)
class Field:
    measurement: str
    visit: str
    field_id: str
    participant_key: str
    source: Citation


@dataclass(frozen=True)
class Search:
    file: str
    available: bool
    citation: Citation | None
    matched_rows: tuple[Field, ...]


CRF, LAB = 'crf_fields.csv', 'lab_feed.csv'
SCHEMA = ['field_id', 'measurement', 'visit', 'participant_key']


def measurement_key(name):
    name = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
    return {
        'hemoglobin a1c': 'hba1c',
        'glycated hemoglobin': 'hba1c',
        'fasting plasma glucose': 'fasting glucose',
    }.get(name, name)


def visit_key(name):
    name = name.strip().lower()
    match = re.fullmatch(r'(?:week|wk|w)\s*(\d+)', name)
    return f'Week {int(match[1])}' if match else name.title()


def read_requirements(case, filename):
    path = case / filename
    records = {}
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.startswith('- ') or '|' not in line:
            continue
        parts = [part.strip() for part in line[2:].split('|')]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f'{filename}:{number}: expected ID | measurement | visit(s)')
        outcome, measurement, visit_list = parts
        visits = tuple(visit_key(item) for item in visit_list.split(';'))
        if outcome in records or not all(visits) or len(set(visits)) != len(visits):
            raise ValueError(f'{filename}:{number}: duplicate outcome or invalid visits')
        records[outcome] = Requirement(outcome, measurement, visits, Citation(filename, number, line))
    if not records:
        raise ValueError(f'{filename}: no outcome definitions found')
    return records


def search_fields(case, filename, requirement):
    path = case / filename
    if not path.is_file():
        return Search(filename, False, None, ())
    with path.open(newline='', encoding='utf-8-sig') as file:
        reader = csv.reader(file, strict=True)
        if next(reader, None) != SCHEMA:
            raise ValueError(f'{filename}: expected CSV header {", ".join(SCHEMA)}')
        matches = []
        while True:
            number = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if not row:
                continue
            if len(row) != len(SCHEMA):
                raise ValueError(f'{filename}:{number}: expected {len(SCHEMA)} columns')
            field_id, measurement, visit, key = (item.strip() for item in row)
            if measurement_key(measurement) == measurement_key(requirement.measurement):
                matches.append(Field(measurement, visit_key(visit), field_id, key,
                                     Citation(filename, number, ' | '.join(row))))
    # The header is a reference to the inspected spec, not evidence of a match.
    return Search(filename, True, Citation(filename, 1, ','.join(SCHEMA)), tuple(matches))


def coverage(requirement, searches):
    return {
        field.visit for search in searches for field in search.matched_rows
        if field.field_id and field.participant_key.lower() == 'participant_id'
    }.intersection(requirement.visits)


def analyze(case, policy):
    requirements = read_requirements(case, 'protocol.md')
    sap = read_requirements(case, 'sap.md') if (case / 'sap.md').is_file() else {}
    findings, trace = [], []

    for requirement in requirements.values():
        def record(actor, event, **details):
            trace.append(dict(outcome=requirement.outcome, actor=actor, event=event, **details))

        planned = sap.get(requirement.outcome)
        aligned = bool(planned and measurement_key(planned.measurement) == measurement_key(requirement.measurement)
                       and set(planned.visits) == set(requirement.visits))
        record('controller', 'read_requirement', protocol=asdict(requirement.source),
               sap=asdict(planned.source) if planned else None, aligned=aligned)
        searches = [search_fields(case, CRF, requirement)]
        record('tool', 'search_fields', **asdict(searches[0]))
        initial_missing = [visit for visit in requirement.visits if visit not in coverage(requirement, searches)]
        initial = ('Provisionally add a CRF field for ' + ', '.join(initial_missing) + ' if no other source covers it.'
                   if initial_missing else 'Keep the existing CRF fields.')
        record('investigator', 'initial_recommendation', detail=initial)

        def inspect_lab():
            result = search_fields(case, LAB, requirement)
            searches.append(result)
            record('tool', 'search_fields', **asdict(result))

        def context():
            matched = coverage(requirement, searches)
            return dict(requirement=asdict(requirement), sap_aligned=aligned,
                        missing_visits=[visit for visit in requirement.visits if visit not in matched],
                        searches=[asdict(search) for search in searches])

        choices = ('inspect_lab', 'submit') if initial_missing else ('submit',)
        action = policy.choose('investigator', context(), choices)
        record('investigator', 'decision', **action)
        if action['action'] == 'inspect_lab':
            inspect_lab()

        for round_number in (1, 2):
            choices = ('accept', 'escalate', 'request_lab') if len(searches) == 1 and initial_missing else ('accept', 'escalate')
            verdict = policy.choose('reviewer', context(), choices)
            record('reviewer', 'verdict', round=round_number, **verdict)
            if verdict['action'] != 'request_lab':
                break
            record('investigator', 'follow_up', action='inspect_lab', reason='Reviewer requested the lab specification.')
            inspect_lab()

        missing = context()['missing_visits']
        evidence_incomplete = len(searches) < 2 or any(not search.available for search in searches)
        if not aligned or verdict['action'] == 'escalate' or (missing and evidence_incomplete):
            status, final = 'unknown', 'Ask the study team to resolve the missing, unverified or conflicting evidence.'
        elif missing:
            status = 'gap_in_supplied_specs'
            final = f'Confirm how {requirement.measurement} will be collected at {", ".join(missing)}.'
        elif initial_missing:
            status = 'covered'
            final = 'Withdraw the proposed CRF addition. The checked specifications cover all required visits.'
        else:
            status, final = 'covered', 'Keep the existing CRF fields.'
        # The controller derives coverage from the visited rows. Model output never supplies a citation or final status.
        record('controller', 'final_finding', status=status, missing_visits=missing, detail=final)
        findings.append(dict(requirement=asdict(requirement), sap=asdict(planned.source) if planned else None,
                             searches=[asdict(search) for search in searches], initial=initial, final=final,
                             status=status, missing_visits=missing))

    return dict(mode=policy.name, findings=findings, trace=trace)


def render_report(run):
    def cite(source):
        return f'`{source["file"]}:{source["line"]}`'

    lines = ['# Protocol-to-data coverage check', '', f'Mode: **{run["mode"]}**', '',
             'This report checks supplied design specifications for a synthetic study.', '']
    labels = {'covered': 'Covered', 'unknown': 'Unknown', 'gap_in_supplied_specs': 'Gap in supplied specifications'}
    for finding in run['findings']:
        req = finding['requirement']
        lines += [f'## {req["outcome"]} · {req["measurement"]} · {", ".join(req["visits"])}', '',
                  f'- **Requirement:** {cite(req["source"])}' + (f' and {cite(finding["sap"])}' if finding['sap'] else ''),
                  f'- **First recommendation:** {finding["initial"]}']
        for search in finding['searches']:
            if not search['available']:
                lines.append(f'- **Search:** `{search["file"]}` unavailable.')
            elif not search['matched_rows']:
                lines.append(f'- **Search:** {cite(search["citation"])} inspected in full. No rows matched the measurement.')
            else:
                rows = ', '.join(f'{cite(row["source"])} ({row["visit"] or "visit unspecified"}, '
                                 f'{row["field_id"] or "field ID missing"}, '
                                 f'{row["participant_key"] or "participant key missing"})' for row in search['matched_rows'])
                lines.append(f'- **Search:** {rows}.')
        verdicts = [event['action'] for event in run['trace']
                    if event['outcome'] == req['outcome'] and event['event'] == 'verdict']
        lines += [f'- **Reviewer:** {", ".join(verdicts)}.',
                  f'- **Final finding:** {labels[finding["status"]]}. {finding["final"]}', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Audit clinical trial data coverage from mock design specifications.')
    parser.add_argument('--case', type=Path, default=Path('data/demo'))
    parser.add_argument('--out', type=Path, default=Path('out'))
    parser.add_argument('--mode', choices=('rules', 'adaption'), default='rules')
    args = parser.parse_args()
    try:
        policy = AdaptionPolicy() if args.mode == 'adaption' else RulesPolicy()
        result = analyze(args.case, policy)
        report = render_report(result)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'trace.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (args.out / 'report.md').write_text(report, encoding='utf-8')
    except (OSError, ValueError, RuntimeError, csv.Error) as error:
        parser.exit(1, f'Run failed: {error}\n')
    print(report)


if __name__ == '__main__':
    main()
