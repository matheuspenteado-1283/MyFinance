import hashlib
import io
import os
import traceback

import pandas as pd
from flask import request, jsonify, send_file, current_app, session
from werkzeug.utils import secure_filename

from . import bp
from .parser import process_file, process_despesas_file, _debug_file
from .db import (
    save_category_rule,
    buscar_receita_por_fingerprint,
    criar_receita,
    criar_importacao,
    salvar_linhas_staging,
    confirmar_importacao,
    descartar_importacao,
    promover_receita,
)
from . import fingerprint, anonymizer, validator, recipes, induction, standard
from .errors import ExtratoError, LayoutDesconhecido, ArquivoIlegivel, ReceitaFalhou
from config import allowed_file
from modules.auth import login_required


def _salvar_upload(file):
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return filepath


def _remover_upload(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass


def _sha256(filepath):
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for bloco in iter(lambda: f.read(65536), b''):
                h.update(bloco)
    except OSError:
        return None
    return h.hexdigest()


def _serializar_transacoes(txns):
    saida = []
    for t in txns:
        saida.append({
            'id': t.get('id', f"linha-{t.get('linha_idx')}"),
            'data': t.get('data'),
            'descricao': t.get('descricao'),
            'valor_original': t.get('valor_original'),
            'moeda': t.get('moeda'),
            'cambio': t.get('cambio', 1.0),
            'valor_eur': t.get('valor_eur'),
            'saldo': t.get('saldo'),
            'is_debit': t.get('is_debit', False),
            'receita': t.get('receita', not t.get('is_debit', False)),
            'categoria': t.get('categoria', 'Não Categorizado'),
            'pag1': t.get('pag1'),
            'pag2': t.get('pag2'),
            'suspeita': t.get('suspeita', False),
            'motivos': t.get('motivos', []),
            'linha_idx': t.get('linha_idx'),
        })
    return saida


def _marcar_suspeitas(txns, resultado):
    suspeitas = set(resultado.linhas_suspeitas)
    for t in txns:
        t['suspeita'] = t.get('linha_idx') in suspeitas


@bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    files = request.files.getlist('files[]')

    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    user_email = session['user_email']
    all_transactions = []
    debug_info = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            try:
                file_transactions = process_file(filepath, user_email=user_email)
                debug_info.append(_debug_file(filepath))
                all_transactions.extend(file_transactions)
            except Exception as e:
                debug_info.append({'file': filename, 'error': str(e),
                                   'trace': traceback.format_exc()})
            finally:
                _remover_upload(filepath)

    if len(all_transactions) == 0:
        return jsonify({
            'error': 'Nenhuma transação foi extraída dos arquivos. Verifique os formatos ou as colunas.',
            'transactions': [],
            'debug': debug_info,
        }), 400

    return jsonify({
        'message': f'Extração concluída: {len(all_transactions)} transações processadas.',
        'transactions': all_transactions,
    }), 200


@bp.route('/save_category', methods=['POST'])
@login_required
def save_category():
    data = request.json
    description = data.get('description')
    category = data.get('category')
    if description and category:
        save_category_rule(description, category, session['user_email'])
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Dados inválidos'}), 400


@bp.route('/export', methods=['POST'])
def export_data():
    data = request.json
    transactions = data.get('transactions', [])

    if not transactions:
        return jsonify({'error': 'Nenhuma transação enviada'}), 400

    for t in transactions:
        p1 = float(t.get('pag1', 0))
        p2 = float(t.get('pag2', 0))
        orig = float(t.get('valor_original', 0))
        diff = abs((p1 + p2) - orig)
        t['diferenca'] = round(diff, 2)
        t['status'] = 'OK' if diff < 0.01 else 'NOK'

    df = pd.DataFrame(transactions)
    cols = ['data', 'descricao', 'valor_original', 'moeda', 'cambio', 'valor_eur', 'pag1', 'pag2', 'diferenca', 'status', 'categoria']
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    df.rename(columns={
        'data': 'Data',
        'descricao': 'Descrição',
        'valor_original': 'Valor Original',
        'moeda': 'Moeda Original',
        'cambio': 'Câmbio EUR',
        'valor_eur': 'Valor Final (EUR)',
        'pag1': 'Pag1',
        'pag2': 'Pag2',
        'diferenca': 'Diferença Original',
        'status': 'Status Pago',
        'categoria': 'Categoria Final',
    }, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Extratos')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Extratos_Processados.xlsx',
    )


# ─────────────────────────────────────────────────────────────────────────────
# Novo fluxo (Fases 1-5): orquestrador com score, receita, revisão
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/extratos/importar', methods=['POST'])
@login_required
def importar():
    user = session['user_email']
    resultados = []

    if 'files[]' not in request.files:
        return jsonify({'erro': 'arquivos_obrigatorios',
                        'mensagem': 'Nenhum arquivo enviado'}), 400

    for file in request.files.getlist('files[]'):
        if not file or not allowed_file(file.filename):
            continue
        filepath = _salvar_upload(file)
        try:
            resultados.append(_processar(filepath, file.filename, user,
                                         request.form.get('conta_bancaria')))
        except ExtratoError as e:
            importacao_id = _criar_importacao_falha(user, file.filename, e)
            resultados.append({**e.to_dict(), 'importacao_id': importacao_id,
                               'arquivo': file.filename})
        except Exception as e:
            importacao_id = _criar_importacao_falha(user, file.filename, e)
            resultados.append({'erro': 'erro_extrato', 'mensagem': str(e),
                               'importacao_id': importacao_id,
                               'arquivo': file.filename})
        finally:
            _remover_upload(filepath)

    if all('erro' in r for r in resultados):
        return jsonify({'importacoes': resultados}), 422
    return jsonify({'importacoes': resultados}), 200


def _criar_importacao_falha(user, nome, erro):
    try:
        return criar_importacao(user, nome, status='descartada', total_linhas=0)
    except Exception:
        return None


def _processar(filepath, nome, user, conta):
    txns = standard.try_parse(filepath)
    receita = None

    if txns is None:
        fp, evid = fingerprint.compute(filepath)
        receita = buscar_receita_por_fingerprint(fp)

        if receita is None:
            sample = anonymizer.build_sample(filepath)
            spec = induction.induzir(sample)
            if spec is None:
                raise LayoutDesconhecido(
                    'Não foi possível identificar as colunas deste extrato.',
                    detalhe={'fingerprint': fp, 'evidencia': evid},
                )
            receita = criar_receita(fp, spec, origem='llm', criada_por=user)

        txns = recipes.apply(receita['spec'], filepath)

    ctx = validator.contexto_do_arquivo(filepath)
    res = validator.validate(txns, **ctx)
    _marcar_suspeitas(txns, res)

    precisa_revisao = (
        receita is None
        or receita['status'] != 'verified'
        or res.score < validator.LIMIAR_AUTO
    )

    checks_payload = [c.__dict__ for c in res.checks]
    importacao_id = criar_importacao(
        user, nome,
        arquivo_sha256=_sha256(filepath),
        fingerprint=(receita or {}).get('fingerprint'),
        receita_id=(receita or {}).get('id'),
        conta_bancaria=conta,
        score=res.score,
        checks=checks_payload,
        total_linhas=len(txns),
        status='pendente',
    )
    salvar_linhas_staging(importacao_id, txns)

    return {
        'importacao_id': importacao_id,
        'arquivo': nome,
        'receita': _receita_resumo(receita),
        'score': res.score,
        'precisa_revisao': precisa_revisao,
        'checks': checks_payload,
        'linhas_suspeitas': res.linhas_suspeitas,
        'total_linhas': len(txns),
        'transacoes': _serializar_transacoes(txns),
    }


def _receita_resumo(receita):
    if not receita:
        return None
    return {
        'id': receita['id'],
        'status': receita['status'],
        'origem': receita['origem'],
        'banco_label': receita['banco_label'],
    }


@bp.route('/extratos/importacoes/<int:importacao_id>/confirmar', methods=['POST'])
@login_required
def confirmar(importacao_id):
    from .db import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT receita_id FROM extrato_importacoes WHERE id = %s',
              (importacao_id,))
    row = c.fetchone()
    conn.close()

    confirmar_importacao(importacao_id)
    if row and row['receita_id']:
        promover_receita(row['receita_id'])
    return jsonify({'status': 'ok'})


@bp.route('/extratos/importacoes/<int:importacao_id>/descartar', methods=['POST'])
@login_required
def descartar(importacao_id):
    descartar_importacao(importacao_id)
    return jsonify({'status': 'ok'})
