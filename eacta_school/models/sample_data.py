"""Données d'exemple : chaque générateur ne s'exécute qu'une seule fois par base.

Les fichiers d'exemple sont chargés comme des données (à l'installation et à chaque mise à jour).
Leurs générateurs sont donc relancés à chaque mise à jour : ce garde-fou évite les doublons.
Pour ne jamais générer d'exemples, définir le paramètre système
« eacta_school.sample_data_disabled » à True avant l'installation.
"""


from lxml import etree

from odoo.tools import file_open

# Clés uniques des enregistrements d'exemple : un enregistrement existant avec la même clé est réutilisé
SAMPLE_KEYS = {
    'eacta.academic.year': ['name'],
    'eacta.class': ['name', 'academic_year_id'],
    'eacta.course': ['code'],
    'eacta.course.category': ['name'],
    'eacta.transport.line': ['code'],
    'res.users': ['login'],
    'library.book': ['isbn'],
}


def adopt_existing_records(env, module, path):
    """Rattache aux identifiants d'un fichier d'exemple les enregistrements déjà présents en base.

    À appeler avant le chargement du fichier : un enregistrement existant (même nom d'année, même code
    de cours, même ISBN...) reçoit l'identifiant XML de l'exemple, qui n'est alors pas recréé. Cela évite
    les erreurs d'unicité lors de la mise à jour d'une base déjà utilisée.
    """
    IMD = env['ir.model.data'].sudo()
    with file_open(path, 'rb') as f:
        root = etree.parse(f).getroot()
    for rec in root.iter('record'):
        model = rec.get('model')
        if model not in SAMPLE_KEYS and model != 'eacta.term':
            continue
        rec_module, _dot, name = rec.get('id').rpartition('.')
        rec_module = rec_module or module
        if IMD.search_count([('module', '=', rec_module), ('name', '=', name)]):
            continue
        values = {}
        for field in rec.findall('field'):
            if field.get('ref'):
                ref = field.get('ref') if '.' in field.get('ref') else f"{module}.{field.get('ref')}"
                target = env.ref(ref, raise_if_not_found=False)
                values[field.get('name')] = target.id if target else None
            else:
                values[field.get('name')] = (field.text or '').strip()
        if model == 'eacta.term':
            # Un trimestre qui chevauche les dates de l'exemple dans la même année est réutilisé
            if not (values.get('academic_year_id') and values.get('date_start') and values.get('date_end')):
                continue
            domain = [('academic_year_id', '=', values['academic_year_id']),
                      ('date_start', '<=', values['date_end']), ('date_end', '>=', values['date_start'])]
        else:
            keys = SAMPLE_KEYS[model]
            if any(values.get(k) in (None, '') for k in keys):
                continue
            domain = [(k, '=', values[k]) for k in keys]
        existing = env[model].sudo().with_context(active_test=False).search(domain, limit=1)
        if existing:
            IMD.create({'module': rec_module, 'name': name, 'model': model, 'res_id': existing.id,
                        'noupdate': True})


def sample_records(env, model, module='eacta_school'):
    """Enregistrements d'un modèle créés (ou réutilisés) par les fichiers d'exemple d'un module."""
    ids = env['ir.model.data'].sudo().search([('module', '=', module), ('model', '=', model)]).mapped('res_id')
    return env[model].browse(ids).exists()


def sample_data_step(env, key, model=None, domain=None):
    """Retourne True la première fois pour `key`, False ensuite.

    Si `model` est donné et contient déjà des enregistrements (`domain`), l'étape est considérée
    comme faite : une base où ces données existent déjà n'est pas complétée une seconde fois.
    """
    ICP = env['ir.config_parameter'].sudo()
    if ICP.get_param('eacta_school.sample_data_disabled') in ('True', '1'):
        return False
    param = f'eacta_school.sample_data_done.{key}'
    if ICP.get_param(param):
        return False
    ICP.set_param(param, 'True')
    if model and env[model].sudo().with_context(active_test=False).search_count(domain or []):
        return False
    return True
