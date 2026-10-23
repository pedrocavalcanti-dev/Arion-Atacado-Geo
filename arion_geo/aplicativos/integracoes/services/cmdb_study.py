"""Read-only, in-memory inventory and comparison for CMDB discovery."""
from collections import Counter, defaultdict
import json
import logging
import re
import time
from xml.etree import ElementTree

from ..clients.cmdb import CMDBClient
from .errors import CMDBAuthenticationError, CMDBInvalidResponseError, CMDBTimeoutError, CMDBUnavailableError, CMDBTLSFailure

logger = logging.getLogger(__name__)

SEARCH_LIMITS = (10, 100, 500, 1000, 5000, None)
SENSITIVE_NAMES = ("password", "passwd", "pwd", "senha", "secret", "token", "credential", "auth", "session", "cookie", "apikey", "privatekey")
SAFE_SAMPLE_FIELDS = {"tipo", "estado", "uf", "curdeplstate", "curdeplstatetype", "curincistate", "curincistatetype", "deplstate", "deplstatetype", "incistate", "incistatetype"}
STATE_FIELDS = ("CurDeplState", "CurDeplStateType", "CurInciState", "CurInciStateType", "DeplState", "DeplStateType", "InciState", "InciStateType")
MAPPING = {
    "Number": "config_item_id", "Name": "name", "Designacao": "designation_arion",
    "DesignacaoOperadora": "operator_designation", "Circuito": "circuit", "ISP": "isp_raw",
    "Cidade": "city", "Estado": "uf_raw", "Tipo": "link_type", "Velocidade": "speed_raw",
    "RangeIP": "range_ip", "CurDeplState": "deployment_state", "CurInciState": "incident_state",
}


def _norm(value):
    return "".join(char.casefold() for char in str(value) if char.isalnum())


def _empty(value):
    return value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}


def _scalar(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _xml_fields(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        root = ElementTree.fromstring(value)
    except ElementTree.ParseError:
        return {"[XML inválido]": value}
    result = {}
    for node in root.iter():
        if node is root or list(node):
            continue
        result[node.tag.split("}")[-1]] = node.text or ""
    return result


def _fields(item):
    output = {key: value for key, value in item.items() if key != "CIXMLData"}
    output.update(_xml_fields(item.get("CIXMLData")))
    return output


def _scan_association_paths(value, path=""):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            current = f"{path}.{key}" if path else str(key)
            norm = _norm(key)
            if any(token in norm for token in ("ticket", "link", "relation", "associated", "linkedobject")):
                found.add(current)
            found.update(_scan_association_paths(child, current))
    elif isinstance(value, list):
        for child in value:
            found.update(_scan_association_paths(child, path))
    return found


def _field_metrics(items):
    stats = defaultdict(lambda: {"exists": 0, "filled": 0, "types": set(), "samples": set()})
    for item in items:
        for key, value in _fields(item).items():
            entry = stats[str(key)]
            entry["exists"] += 1
            if not _empty(value):
                entry["filled"] += 1
                if isinstance(value, bool): entry["types"].add("boolean")
                elif isinstance(value, (int, float)): entry["types"].add("number")
                elif isinstance(value, (dict, list)): entry["types"].add(type(value).__name__)
                else: entry["types"].add("string")
                if _norm(key) in SAFE_SAMPLE_FIELDS and len(entry["samples"]) < 5:
                    sample = _scalar(value)
                    if sample and len(sample) <= 100:
                        entry["samples"].add(sample)
    result = {}
    for key, entry in stats.items():
        result[key] = {
            "exists": entry["exists"], "filled": entry["filled"],
            "empty": entry["exists"] - entry["filled"],
            "percent": round(entry["filled"] * 100 / entry["exists"], 1) if entry["exists"] else 0,
            "types": sorted(entry["types"]), "samples": sorted(entry["samples"]),
            "sensitive": any(part in _norm(key) for part in SENSITIVE_NAMES),
        }
    return result


class CMDBStudyService:
    def __init__(self, client, *, progress=print, retry_delay=0.5):
        self.client = client
        self.progress = progress
        self.retry_delay = retry_delay
        self.calls = 0
        self.auth_failed = False

    def run(self, base_rows):
        started = time.perf_counter()
        link_search = self._search_class("Links de internet")
        links, link_fetch = self._fetch_class("Links de internet", link_search["ids"])
        operator_search = self._search_class("Operadoras")
        operators, operator_fetch = self._fetch_class("Operadoras", operator_search["ids"])
        base = list(base_rows)
        comparison = self._compare_base(links, base)
        link_fields = _field_metrics(links)
        operator_fields = _field_metrics(operators)
        relation = self._resolve_isp(links, operators)
        result = {
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
            "duration_seconds": round(time.perf_counter() - started, 1), "calls": self.calls,
            "batch_size": self.client.batch_size,
            "links": self._class_result(link_search, link_fetch, links, link_fields),
            "operators": self._class_result(operator_search, operator_fetch, operators, operator_fields),
            "relation": relation, "comparison": comparison, "base_count": len(base),
            "ticket_paths": sorted(set().union(*(_scan_association_paths(item) for item in links + operators))) if links or operators else [],
        }
        result["complete"] = all(value["complete"] for value in (result["links"], result["operators"]))
        result["report"] = self.render_report(result)
        result["links"].pop("items", None)
        result["operators"].pop("items", None)
        return result

    def _search_class(self, class_name):
        observations = []
        succeeded = []
        if self.auth_failed:
            return {"observations": [{"limit": "não executado", "count": 0, "duration_ms": 0, "error": "authentication"}], "ids": [], "selected_limit": "nenhum", "search_success": False, "hit_cap": False}
        for limit in SEARCH_LIMITS:
            label = "sem limite" if limit is None else str(limit)
            started = time.perf_counter()
            try:
                ids = self._retry(lambda: self.client.search_item_ids(class_name=class_name, limit=limit))
                record = {"limit": label, "ids": ids, "count": len(ids), "duration_ms": int((time.perf_counter() - started) * 1000), "error": ""}
                succeeded.append(record)
            except Exception as exc:
                record = {"limit": label, "ids": [], "count": 0, "duration_ms": int((time.perf_counter() - started) * 1000), "error": type(exc).__name__}
                if isinstance(exc, CMDBAuthenticationError):
                    self.auth_failed = True
            observations.append({key: value for key, value in record.items() if key != "ids"})
            logger.info("CMDB study class=%s operation=Search limit=%s result_count=%s duration_ms=%s error=%s", class_name, label, record["count"], record["duration_ms"], record["error"] or "none")
            if self.auth_failed:
                break
        selected = max(succeeded, key=lambda row: (row["count"], row["limit"] == "sem limite"), default=None)
        ids = list(dict.fromkeys(selected["ids"])) if selected else []
        hit_cap = bool(selected and (selected["count"] >= self.client.MAX_STUDY_LIMIT or (selected["limit"] != "sem limite" and selected["count"] >= int(selected["limit"]))))
        return {"observations": observations, "ids": ids, "selected_limit": selected["limit"] if selected else "nenhum", "search_success": bool(succeeded), "hit_cap": hit_cap}

    def _fetch_class(self, class_name, ids):
        batch_size = self.client.batch_size
        items, failures, successful_batches = [], [], 0
        total_batches = (len(ids) + batch_size - 1) // batch_size
        for offset in range(0, len(ids), batch_size):
            batch = ids[offset:offset + batch_size]
            batch_number = offset // batch_size + 1
            before = len(items)
            self._fetch_batch(class_name, batch, batch_number, items, failures)
            if len(items) > before:
                successful_batches += 1
            if batch_number % 5 == 0 or batch_number == total_batches:
                self.progress(f"[CMDB] {class_name}: {min(offset + batch_size, len(ids))}/{len(ids)}")
        complete = not failures and len(items) == len(ids)
        return items, {"expected": len(ids), "processed": len(items), "failures": failures, "batches": total_batches, "successful_batches": successful_batches, "complete": complete}

    def _fetch_batch(self, class_name, ids, batch_number, items, failures):
        if not ids: return
        started = time.perf_counter()
        try:
            fetched = self._retry(lambda: self.client.get_items(ids))
            items.extend(CMDBClient.sanitize_study_items(fetched))
            logger.info("CMDB study class=%s operation=Get batch=%s items=%s duration_ms=%s", class_name, batch_number, len(ids), int((time.perf_counter()-started)*1000))
        except (CMDBAuthenticationError,):
            failures.append({"batch": batch_number, "count": len(ids), "error": "authentication"})
        except CMDBInvalidResponseError:
            if len(ids) == 1:
                failures.append({"batch": batch_number, "count": 1, "error": "invalid_response"})
                return
            midpoint = len(ids) // 2
            self._fetch_batch(class_name, ids[:midpoint], batch_number, items, failures)
            self._fetch_batch(class_name, ids[midpoint:], batch_number, items, failures)
        except Exception as exc:
            failures.append({"batch": batch_number, "count": len(ids), "error": type(exc).__name__})

    def _retry(self, callback):
        for attempt in range(3):
            try:
                self.calls += 1
                result = callback()
                return result
            except (CMDBAuthenticationError, CMDBInvalidResponseError):
                raise
            except (CMDBTimeoutError, CMDBUnavailableError, CMDBTLSFailure):
                if attempt == 2: raise
                time.sleep(self.retry_delay * (attempt + 1))

    @staticmethod
    def _class_result(search, fetch, items, fields):
        definition = defaultdict(lambda: {"count": 0, "fields": set()})
        states = defaultdict(Counter)
        versions = {"VersionID": Counter(), "LastVersionID": Counter(), "same": 0, "different": 0, "missing": 0}
        config_item_ids, numbers = [], []
        for item in items:
            definition[str(item.get("DefinitionID", "não informado"))]["count"] += 1
            definition[str(item.get("DefinitionID", "não informado"))]["fields"].update(_fields(item))
            flat = _fields(item)
            for field in STATE_FIELDS:
                if field in flat and not _empty(flat[field]): states[field][_scalar(flat[field])] += 1
            config_item_id, number = _scalar(item.get("ConfigItemID")), _scalar(item.get("Number"))
            if config_item_id: config_item_ids.append(config_item_id)
            if number: numbers.append(number)
            if config_item_id and number and config_item_id == number: versions["same_id_number"] = versions.get("same_id_number", 0) + 1
            version, last_version = _scalar(item.get("VersionID")), _scalar(item.get("LastVersionID"))
            if version: versions["VersionID"][version] += 1
            if last_version: versions["LastVersionID"][last_version] += 1
            if not version or not last_version: versions["missing"] += 1
            elif version == last_version: versions["same"] += 1
            else: versions["different"] += 1
        return {
            "search": search["observations"], "search_limit": search["selected_limit"],
            "search_complete": search["search_success"] and search["selected_limit"] == "sem limite" and not search["hit_cap"],
            "ids_found": len(search["ids"]), "fields": fields,
            "definitions": {key: {"count": value["count"], "fields": sorted(value["fields"])} for key, value in definition.items()},
            "states": {field: dict(counts) for field, counts in states.items()},
            "versions": {"VersionID": dict(versions["VersionID"]), "LastVersionID": dict(versions["LastVersionID"]), "same": versions["same"], "different": versions["different"], "missing": versions["missing"]},
            "identity": {"config_item_ids": len(config_item_ids), "unique_config_item_ids": len(set(config_item_ids)), "numbers": len(numbers), "unique_numbers": len(set(numbers)), "equal_id_and_number": versions.get("same_id_number", 0)},
            "fetch": fetch, "items": items,
            "complete": fetch["complete"] and search["search_success"] and search["selected_limit"] == "sem limite" and not search["hit_cap"],
        }

    @staticmethod
    def _compare_base(links, base_rows):
        cmdb_numbers = [_scalar(item.get("Number")) for item in links if not _empty(item.get("Number"))]
        base_ids = [_scalar(row.get("config_item_id")) for row in base_rows if not _empty(row.get("config_item_id"))]
        cmdb_set, base_set = set(cmdb_numbers), set(base_ids)
        duplicates_cmdb = [value for value, count in Counter(cmdb_numbers).items() if count > 1]
        duplicates_base = [value for value, count in Counter(base_ids).items() if count > 1]
        matches = []
        fields = defaultdict(Counter)
        by_base = { _scalar(row.get("config_item_id")): row for row in base_rows if not _empty(row.get("config_item_id")) }
        for item in links:
            number = _scalar(item.get("Number"))
            row = by_base.get(number)
            if not row: continue
            matches.append(number)
            flat = _fields(item)
            for source, target in MAPPING.items():
                if source not in flat: continue
                cmdb, arion = _scalar(flat[source]), _scalar(row.get(target))
                fields[source]["compared"] += 1
                fields[source]["equal" if cmdb == arion else "different"] += 1
        return {"cmdb_numbers": len(cmdb_numbers), "base_rows": len(base_ids), "matches": len(set(matches)), "cmdb_only": len(cmdb_set-base_set), "base_only": len(base_set-cmdb_set), "duplicate_cmdb": len(duplicates_cmdb), "duplicate_base": len(duplicates_base), "fields": {key: dict(value) for key,value in fields.items()}}

    @staticmethod
    def _resolve_isp(links, operators):
        indexes = {"ConfigItemID": defaultdict(list), "Number": defaultdict(list), "Name": defaultdict(list)}
        other_indexes = defaultdict(lambda: defaultdict(list))
        for operator in operators:
            for key in indexes:
                value = _scalar(operator.get(key))
                if value: indexes[key][value].append(operator)
            attrs = _xml_fields(operator.get("CIXMLData"))
            for key, value in attrs.items():
                if "cnpj" in _norm(key):
                    scalar = _scalar(value)
                    if scalar: other_indexes[key][scalar].append(operator)
        result = Counter(); samples = []
        for link in links:
            isp = _scalar(_xml_fields(link.get("CIXMLData")).get("ISP"))
            if not isp: result["empty"] += 1; continue
            matches = [(method, values[isp]) for method, values in indexes.items() if isp in values]
            matches += [(f"CIXMLData.{field}", values[isp]) for field, values in other_indexes.items() if isp in values]
            unique = {str(item.get("ConfigItemID", id(item))): (method, item) for method, rows in matches for item in rows}
            if len(unique) > 1:
                result["ambiguous"] += 1; method, operator = "ambiguous", None
            elif unique:
                method, operator = next(iter(unique.values())); result[method] += 1
            else:
                method, operator = "unresolved", None; result[method] += 1
            if operator and len(samples) < 5:
                samples.append({"link_id": _scalar(link.get("ConfigItemID")), "link_number": _scalar(link.get("Number")), "link_name": _scalar(link.get("Name"))[:80], "isp": isp, "operator_id": _scalar(operator.get("ConfigItemID")), "operator_number": _scalar(operator.get("Number")), "operator_name": _scalar(operator.get("Name"))[:80], "method": method})
        result["total_links"] = len(links); result["with_isp"] = len(links) - result["empty"]
        matched_methods = [key for key in ("ConfigItemID", "Number", "Name") if result[key]]
        other_matches = [key for key in result if key.startswith("CIXMLData.") and result[key]]
        conclusion = matched_methods[0] if len(matched_methods) == 1 and not other_matches else "other" if other_matches and not matched_methods else "mixed" if matched_methods or other_matches else "inconclusive"
        return {"counts": dict(result), "samples": samples, "conclusion": conclusion}

    @staticmethod
    def render_report(result):
        def field_table(fields):
            rows = ["| Campo | Existe | Preenchido | Vazio | % | Tipos | Exemplo seguro |", "|---|---:|---:|---:|---:|---|---|"]
            for name, metric in sorted(fields.items(), key=lambda pair: (-pair[1]["filled"], pair[0].casefold())):
                example = "[PROTEGIDO]" if metric["sensitive"] else ", ".join(metric["samples"][:3]) or "—"
                rows.append(f"| {name} | {metric['exists']} | {metric['filled']} | {metric['empty']} | {metric['percent']}% | {', '.join(metric['types']) or '—'} | {example} |")
            return "\n".join(rows)
        links, operators, relation, comparison = result["links"], result["operators"], result["relation"], result["comparison"]
        resolve = relation["counts"]
        designation_candidates = ("Designacao", "DesignacaoOperadora", "Circuito", "Identificacao", "Name")
        designation_measured = [key for key in designation_candidates if comparison["fields"].get(key, {}).get("compared")]
        designation_best = max(
            designation_measured,
            key=lambda key: comparison["fields"][key].get("equal", 0) / comparison["fields"][key]["compared"],
            default="inconclusivo",
        )
        designation_summary = ", ".join(
            f"{key} {comparison['fields'][key].get('equal', 0)}/{comparison['fields'][key]['compared']}"
            for key in designation_measured
        )
        report = f'''# Estudo real do CMDB ServiceUp

## Resumo executivo

Status: **{'Completo' if result['complete'] else 'Parcial'}**. Links encontrados/processados: {links['ids_found']}/{links['fetch']['processed']}. Operadoras encontradas/processadas: {operators['ids_found']}/{operators['fetch']['processed']}. Duração: {result['duration_seconds']} s; chamadas/retries de client contabilizados: {result['calls']}.

## Ambiente e método

Execução somente leitura via `CMDBClient` existente, com configuração e credenciais DPAPI atuais descriptografadas apenas em memória. Nenhum payload ou valor sensível foi persistido. A Base XLSX/Arion foi consultada somente para comparação ({comparison['base_rows']} registros); não foi alterada.

## Limitações da API

Não foi assumido offset/cursor. Paginação: não documentada/não encontrada. Resultado completo exige Search sem limite ou limites que não aparentem truncamento; lotes com falha deixam o estudo parcial. Definições e valores representam apenas as versões retornadas pela API durante esta execução.

## Comportamento do ConfigItemSearch

| Limite | IDs retornados | Duração ms | Erro |
|---:|---:|---:|---|
{''.join(f"| {row['limit']} | {row['count']} | {row['duration_ms']} | {row['error'] or '—'} |\n" for row in links['search'])}{''.join(f"| Operadoras · {row['limit']} | {row['count']} | {row['duration_ms']} | {row['error'] or '—'} |\n" for row in operators['search'])}

Search utilizou `Class` e `Limit`; não foi confirmada paginação.

## Comportamento do ConfigItemGet

Links: {links['fetch']['processed']}/{links['fetch']['expected']} itens processados em {links['fetch']['batches']} lotes, com {len(links['fetch']['failures'])} falhas. Operadoras: {operators['fetch']['processed']}/{operators['fetch']['expected']} itens em {operators['fetch']['batches']} lotes, com {len(operators['fetch']['failures'])} falhas. `ConfigItemGet` usou lote de {result['batch_size']} IDs.

## Links de internet

Encontrados: {links['ids_found']}; processados: {links['fetch']['processed']}; falhas: {len(links['fetch']['failures'])}.

### Campos encontrados e taxa de preenchimento

{field_table(links['fields'])}

### Campos por DefinitionID

{chr(10).join(f"- DefinitionID {key}: {value['count']} itens; campos: {', '.join(value['fields'])}" for key,value in sorted(links['definitions'].items())) or 'Não identificado nos itens processados.'}

### Estados



{chr(10).join(f"- {field}: {', '.join(f'{value} ({count})' for value,count in counts.items())}" for field,counts in links['states'].items()) or 'Nenhum estado preenchido observado.'}

### Versionamento

VersionID distintos: {len(links['versions']['VersionID'])}; LastVersionID distintos: {len(links['versions']['LastVersionID'])}. Iguais: {links['versions']['same']}; diferentes: {links['versions']['different']}; ausente em um dos campos: {links['versions']['missing']}.

## Operadoras

Encontradas: {operators['ids_found']}; processadas: {operators['fetch']['processed']}; falhas: {len(operators['fetch']['failures'])}.

### Campos encontrados e taxa de preenchimento

{field_table(operators['fields'])}


### Campos sensiveis

Os campos sensiveis aparecem somente por presenca e quantidade preenchida, com conteudo `[PROTEGIDO]` e classificacao `PROTEGIDO - NAO PERSISTIR`. Exemplos nao sao divulgados para UsuarioPPOE, contatos, CNPJ ou MAC.

## Relação Link → Operadora

ISP resolvido por ConfigItemID: {resolve.get('ConfigItemID',0)}; por Number: {resolve.get('Number',0)}; por Name: {resolve.get('Name',0)}; por outro campo: {sum(value for key,value in resolve.items() if key.startswith('CIXMLData.'))}; não resolvido: {resolve.get('unresolved',0)}; ambíguo: {resolve.get('ambiguous',0)}; ISP vazio: {resolve.get('empty',0)}.

Conclusão observada para ISP: **{relation['conclusion']}**. A resolução usa correspondência exata de strings sem conversão numérica, preservando zeros.

| Link ConfigItemID | Link Number | Link Name | ISP | Operadora ConfigItemID | Operadora Number | Operadora Name | Método |
|---|---|---|---|---|---|---|---|
{''.join(f"| {row['link_id']} | {row['link_number']} | {row['link_name']} | {row['isp']} | {row['operator_id']} | {row['operator_number']} | {row['operator_name']} | {row['method']} |\n" for row in relation['samples'])}

## ConfigItemID vs Number
ConfigItemID presente/unico: {links['identity']['config_item_ids']}/{links['identity']['unique_config_item_ids']}; Number presente/unico: {links['identity']['numbers']}/{links['identity']['unique_numbers']}; valores iguais entre si: {links['identity']['equal_id_and_number']}.

`ConfigItemID` foi tratado como identificador técnico da API e `Number` comparado literalmente com o campo XLSX/Arion `ConfigItem#` (`CMDBLink.config_item_id`). Correspondências exatas: {comparison['matches']}; somente CMDB: {comparison['cmdb_only']}; somente Base: {comparison['base_only']}; duplicados Number: {comparison['duplicate_cmdb']}; duplicados na Base: {comparison['duplicate_base']}. Resultado: **{'Sim' if comparison['matches'] and not comparison['cmdb_only'] and not comparison['base_only'] else 'Parcialmente' if comparison['matches'] else 'Inconclusivo'}**.

## Comparação com Base atual

{comparison['matches']} Numbers coincidem exatamente com `ConfigItem#` em {comparison['base_rows']} linhas da Base consultada. Não houve normalização numérica. Comparações por campo: {json.dumps(comparison['fields'], ensure_ascii=False, sort_keys=True)}.

## Designação

Campos avaliados: Designacao, DesignacaoOperadora, Circuito, Identificacao e Name. Igualdades com `designation_arion`: {designation_summary}. Campo com maior igualdade observada: **{designation_best}**. Tratar como forte evidencia de equivalencia de valor; validar a semantica antes de adota-lo como regra oficial.

## Projeto / Cliente

Campos explícitos com nome Projeto/Project: {', '.join(name for name in list(links['fields'])+list(operators['fields']) if 'projet' in _norm(name) or 'project' in _norm(name)) or 'não encontrados'}. `CustomerID` foi inventariado como possível campo candidato, sem evidência suficiente para tratá-lo como Projeto. Resultado: **fonte oficial de Projeto não confirmada pela API estudada**.

## Possíveis associações com Ticket

Resultado direto: **{"Sim" if result['ticket_paths'] else "Nao encontrado"}**. A busca considerou nomes contendo Ticket, Link, Relation, Associated e estruturas equivalentes.

Chaves/estruturas com indícios de Ticket/associação encontrados: {', '.join(result['ticket_paths']) or 'nenhum campo ou estrutura correspondente foi exposto em Search/Get'}.

## Qualidade de dados

- ConfigItemID duplicados: {links['identity']['config_item_ids'] - links['identity']['unique_config_item_ids']}.
- Number duplicados no CMDB/Base: {comparison['duplicate_cmdb']}/{comparison['duplicate_base']}.
- Name vazio: {links['fields'].get('Name', {}).get('empty', 'campo ausente')}; ISP vazio/nao resolvido: {resolve.get('empty', 0)}/{resolve.get('unresolved', 0)}.
- Preenchimentos parciais e valores atipicos estao detalhados no inventario e nao sao classificados automaticamente como erro.

## Divergências

- Status do estudo: {'Completo para o inventário recuperado' if result['complete'] else 'Parcial; consultar erros abaixo'}.
- Number duplicado no CMDB/Base: {comparison['duplicate_cmdb']}/{comparison['duplicate_base']}.
- ISP sem operadora: {resolve.get('unresolved',0)}; ISP ambíguo: {resolve.get('ambiguous',0)}.
- Falhas de Get: Links {len(links['fetch']['failures'])}; Operadoras {len(operators['fetch']['failures'])}.

## Matriz de mapeamento e recomendacoes para o modelo futuro

| Campo CMDB | Campo Arion atual | Decisão futura |
|---|---|---|
| ConfigItemID | config_item_id | CONFIRMAR como chave técnica, comparar com base |
| Number | ConfigItem# / config_item_id | Candidato; evidência quantitativa acima |
| Name | name | Candidato |
| Designacao / DesignacaoOperadora / Circuito / Identificacao | designation_arion / operator_designation / circuit | Investigar comparações acima |
| ISP | Provider/Operadora | Candidato; usar resolução medida |
| Cidade / Estado / Tipo / Velocidade / RangeIP | city / uf_raw / link_type / speed_raw / range_ip | Candidatos |
| CurDeplState / CurInciState | deployment_state / incident_state | Candidatos |
| Senhas, tokens, secrets, sessões | — | PROTEGIDO — NÃO PERSISTIR |

## Pendências

- Search não documenta offset/cursor; validar truncamento junto ao administrador do GenericInterface se o resultado atingir o teto observado.
- Campos ausentes ou com valor `Operational` em Designacao são reportados sem classificação automática de erro.
- Nenhuma alteração, sync ou escrita foi executada no CMDB ou Base.

## Próxima fase: OTRS / NOC - ATACADO

Investigar MySQL read-only: **Queue → Tickets → associação oficial ao ConfigItem**, começando pela fila `NOC - ATACADO`. Levar `ConfigItemID`, `Number`/`ConfigItem#`, `Name`, `Designacao`, `DesignacaoOperadora`, `Circuito` e identificadores de operadora descobertos. Não usar `ticket.title LIKE` como relação definitiva.

## Guia para investigacao OTRS

Procurar as estruturas oficiais de associacao pelos identificadores `ConfigItemID`, `Number`/`ConfigItem#`, `Designacao` e `Name`, partindo de `Queue` -> tickets da fila `NOC - ATACADO` -> vinculo ConfigItem. O titulo pode apoiar a investigacao, mas nao confirma a relacao.


'''
        return report
