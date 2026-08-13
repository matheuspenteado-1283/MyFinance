class ExtratoError(Exception):
    """Base. Toda falha de extração é uma destas — nunca um except genérico."""
    codigo = 'erro_extrato'

    def __init__(self, mensagem, detalhe=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhe = detalhe

    def to_dict(self):
        return {'erro': self.codigo, 'mensagem': self.mensagem, 'detalhe': self.detalhe}


class FormatoNaoSuportado(ExtratoError):
    codigo = 'formato_nao_suportado'


class ArquivoIlegivel(ExtratoError):
    """PDF corrompido, protegido por senha, XLSX inválido."""
    codigo = 'arquivo_ilegivel'


class LayoutDesconhecido(ExtratoError):
    """Nenhuma receita casou e a indução não produziu spec usável."""
    codigo = 'layout_desconhecido'


class ReceitaFalhou(ExtratoError):
    """A receita existe mas não extraiu nada — provável mudança de layout do banco."""
    codigo = 'receita_falhou'
