import pandas as pd
import os
from datetime import datetime

class PQ():
    def __init__(self, source_dir) -> None:
        items = os.listdir(source_dir)
        m_dates = [os.path.getmtime(os.path.join(source_dir, item)) for item in items]
        for item, _ in sorted(zip(items, m_dates), key=lambda pair: pair[1], reverse=True):  
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'CapEx Engenharia - AWP' in item:
                    print('File used for PQ report: ', item)
                    self.df_scheduler = pd.read_excel(
                        os.path.join(source_dir, item),
                        sheet_name='Geral - Verum OFICIAL',
                        skiprows=10,
                        usecols=['CWP', 'QUANT. DETALHADO CORRIGIDA', 'UNID CORRIGIDA']
                    )
                break

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'CWP': 'cwp', 
            'QUANT. DETALHADO CORRIGIDA': 'peso_total_t',
            'UNID CORRIGIDA': 'un'
        })
        df = df.loc[(df['un']=='t') | (df['un']=='kg')]
        df = df.loc[pd.to_numeric(df['peso_total_t'], errors='coerce').notnull()]
        df.loc[df['un']=='kg', 'peso_total_t'] = df['peso_total_t'] / 1000
        df = df.groupby(by=['cwp'], as_index=False).sum(numeric_only=True)
        df['peso_total_kg'] = df['peso_total_t'] * 1000
        return df
         

class PQSimplified():
    def __init__(self, source_dir) -> None:
        items = os.listdir(source_dir)
        m_dates = [os.path.getmtime(os.path.join(source_dir, item)) for item in items]
        for item, _ in sorted(zip(items, m_dates), key=lambda pair: pair[1]):  
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'pq' in item.lower():
                    self.df_scheduler = pd.read_excel(
                        os.path.join(source_dir, item),
                        sheet_name='Planilha1',
                        usecols=['CWP', 'Peso total (t)', 'Peso total (kg)']
                    )

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'CWP': 'cwp', 
            'Peso total (t)': 'peso_total_t',
            'Peso total (kg)': 'peso_total_kg',
        })
        return df
         


class SuppliersLX():
    def __init__(self, source_dir, mapper_dir, grouped_by_building=False) -> None:
        self.source_dir = source_dir
        self.mapper_dir = mapper_dir
        self.grouped_by_building = grouped_by_building

    def get_report(self):
        self._run_pipeline()
        return self.df_report

    def get_erros(self):
        self._run_pipeline()
        return self.df_errors

    def _run_pipeline(self):
        self._read_mapper()
        self._clean_mapper()
        self._read_files()
        self._clean_raw()
        self.df_report = pd.merge(
            left=self.df_lx,
            right=self.df_mapper,
            on='file_name',
            how='left'
        )
    
    def _read_mapper(self):
        for item in os.listdir(self.mapper_dir):
            item_path = os.path.join(self.mapper_dir, item)
            if os.path.isfile(item_path) and 'lx-fornecedores' in item.lower():
                self.df_mapper = pd.read_excel(
                    item_path,
                    usecols=['Documento', 'Empresa']
                )

    def _clean_mapper(self):
        df = self.df_mapper
        df = df.rename(columns={
            'Documento': 'file_name', 
            'Empresa': 'supplier'
        })
        df['supplier'] = df['supplier'].str.split(' ').str[:2].str.join(' ')
        self.df_mapper = df

    def _read_files(self):
        worksheets = []
        df_errors = pd.DataFrame(columns=['file', 'sheet'])
        for item in os.listdir(self.source_dir):
            if os.path.isfile(os.path.join(self.source_dir, item)):
                try:
                    mod_date = os.path.getmtime(os.path.join(self.source_dir, item))
                    workbook = pd.ExcelFile(os.path.join(self.source_dir, item))
                    for sheet in workbook.sheet_names:
                        if 'rosto' not in sheet.lower():
                            try:
                                worksheet = workbook.parse(
                                    sheet,
                                    skiprows=2,
                                    usecols=['CWP', 'PESO UNIT(KG)', 'C??DIGO DO MATERIAL (SKU)', 'QTDE', 'DESCRI????O COMPLETA', 'OBS', 'TAG DA REFER??NCIA'],
                                    converters={
                                        'CWP': str, 
                                        'C??DIGO DO MATERIAL (SKU)': str, 
                                        'DESCRI????O COMPLETA': str,  
                                        'OBS': str,  
                                        'TAG DA REFER??NCIA': str
                                    }
                                )
                                worksheet['sheet_name'] = sheet
                                worksheet['file_name'] = item.split('.')[0]
                                worksheet['last_mod_date'] = datetime.fromtimestamp(mod_date).strftime('%Y-%m-%d %H:%M:%S')
                                worksheets.append(worksheet)
                            except:
                                row = pd.DataFrame({'file': [item], 'sheet': [sheet]})
                                df_errors = pd.concat([df_errors, row], axis=0, ignore_index=True)          
                except Exception as e:
                    print("Error when reading: ", os.path.join(self.source_dir, item))
                    row = pd.DataFrame({'file': [item], 'sheet': None})
                    df_errors = pd.concat([df_errors, row], axis=0, ignore_index=True)                
        self.df_raw = pd.concat(worksheets, axis=0, ignore_index=True)
        self.df_errors = df_errors

    def _clean_raw(self):
        df = self.df_raw
        df = df.rename(columns={
            'CWP': 'cwp',
            'TAG DA REFER??NCIA': 'cod_ativo',
            'C??DIGO DO MATERIAL (SKU)': 'tag',
            'DESCRI????O COMPLETA': 'descricao',
            'QTDE': 'qtd_lx', 
            'PESO UNIT(KG)': 'peso_un',
            'OBS': 'obs'
        })
        df = df.dropna(subset=['cwp', 'tag', 'qtd_lx'])
        df['cwp'] = df['cwp'].str.replace(' ', '')
        df['tag'] = df['tag'].str.replace(' ', '')
        
        df.loc[~df['obs'].str.contains('N??O MODELAD', na=False), 'geometry'] = True
        df.loc[df['obs'].str.contains('N??O MODELAD', na=False), 'geometry'] = False

        df['cwp_number'] = df['cwp'].str.split('-').str[-1]
        df['chave'] = df['cwp_number'].str.zfill(3) + '-' + df['tag']
        df.loc[df['peso_un'].str.contains(',', na=False, regex=False), 'peso_un'] = df['peso_un'].str.replace('.', '').str.replace(',', '.')
        df['peso_un'] = df['peso_un'].apply(lambda x: 0 if '-' in str(x) else float(x))
        df['qtd_lx'] = df['qtd_lx'].astype(float)

        keys = ['cwp', 'cod_ativo', 'tag'] if self.grouped_by_building else ['cwp', 'tag']
        df_numeric = df[keys + ['qtd_lx']].groupby(by=keys, as_index=False).sum(numeric_only=True).round(0)
        df_categorical = df.copy().drop(columns=['qtd_lx']).drop_duplicates(subset=keys, keep='first')
        df = pd.merge(df_numeric, df_categorical, how='left', on=keys)

        self.df_lx = df


class CronogramaMasterConstrucap:
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'construcap' in item.lower():
                    self.df_workbook = pd.read_excel(
                        os.path.join(source_dir, item),
                        usecols=['N??vel', 'P0400: cwa_id', "P0400: CWP's / EWP's / PWP's_Work_Type", 'Activity Name', 'Start', 'Finish']
                    )
                    break
    
    def get_report(self):
        return self.__class__._clean_report(self.df_workbook)

    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'N??vel': 'nivel',
            'P0400: cwa_id': 'cwa',
            "P0400: CWP's / EWP's / PWP's_Work_Type": 'cwp',
            'Activity Name': 'descricao',
            'Start': 'data_inicio',
            'Finish': 'data_termino'
        })
        df = df.loc[df['nivel'] > 3]
        df = df.dropna(subset=['cwp'])
        df.loc[df['cwp'].str.contains('-CWPp'), 'atividade'] = 'pre-montagem'
        df.loc[df['cwp'].str.contains('-CWPm'), 'atividade'] = 'montagem'
        df['cwp'] = df['cwp'].str.split('-CWP').str[0] + '-CWP'

        df_min = df.loc[df.groupby('cwp', sort=False)['data_inicio'].idxmin()].drop(columns=['data_termino'])
        df_max = df.loc[df.groupby('cwp', sort=False)['data_termino'].idxmax(), ['cwp', 'data_termino']]
        
        df = pd.merge(
            left=df_min,
            right=df_max,
            on='cwp',
            how='outer'
        )
        return df



class Construcap():
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'cronograma construcap' in item.lower():
                    self.df_scheduler = pd.read_excel(
                        os.path.join(source_dir, item),
                        sheet_name='Datas in??cio montagem CWP',
                        usecols=['CWA', 'Descri????o CWA', 'CWP Montagem', 'Descri????o CWP Montagem', 'Data de in??cio de montagem - Real / Tend??ncia Montadora']
                    )

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'CWA': 'cwa', 
            'Descri????o CWA': 'descricao_cwa', 
            'CWP Montagem': 'cwp', 
            'Descri????o CWP Montagem': 'descricao_cwp', 
            'Data de in??cio de montagem - Real / Tend??ncia Montadora': 'data_inicio'
        })
        df.loc[~df['cwp'].str.contains('-CWP'), 'cwp'] = df['cwp'] + '-CWP'
        return df


class Cardan():
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'cronograma cardan' in item.lower():
                    self.df_scheduler = pd.read_excel(
                        os.path.join(source_dir, item),
                        usecols=['CWA', 'CWP', 'Data de in??cio CWP  - Real / Tend??ncia  Construtora', 'Data de t??rmino CWP  - Real / Tend??ncia  Construtora', 'Avan??o Previsto', 'Avan??o Real']
                    )

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'CWA': 'cwa', 
            'CWP': 'cwp', 
            'Data de in??cio CWP  - Real / Tend??ncia  Construtora': 'data_inicio',
            'Data de t??rmino CWP  - Real / Tend??ncia  Construtora': 'data_termino',
            
        })
        df.loc[~df['cwp'].str.contains('-CWP'), 'cwp'] = df['cwp'] + '-CWP'
        return df


class Aumond():
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'aumond' in item.lower():
                    workbook = pd.ExcelFile(os.path.join(source_dir, item))
                    for sheet_name in workbook.sheet_names:
                        if 'aumond' in sheet_name.lower():
                            self.df_scheduler = workbook.parse(
                                sheet_name=sheet_name,
                                usecols=['Start', 'Finish', 'PWP (PWPe/PWP/PWPl)']
                            )
                            break

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'Start': 'data_inicio', 
            'Finish': 'data_termino', 
            'PWP (PWPe/PWP/PWPl)': 'cwp'
        })
        df = df.loc[df['cwp'].str.contains('-PWPl', na=False)]
        df['cwp'] = df['cwp'].str.replace('-PWPl', '')
        df.loc[~df['cwp'].str.contains('-CWP'), 'cwp'] = df['cwp'] + '-CWP'
        return df


class FamStructure():
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'fam estrutura' in item.lower():
                    workbook = pd.ExcelFile(os.path.join(source_dir, item))
                    for sheet_name in workbook.sheet_names:
                        if 'fam' in sheet_name.lower():
                            self.df_scheduler = workbook.parse(
                                sheet_name=sheet_name,
                                usecols=['Start', 'Finish', 'PWP (PWPe/PWP/PWPl)']
                            )
                            break

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'Start': 'data_inicio', 
            'Finish': 'data_termino', 
            'PWP (PWPe/PWP/PWPl)': 'cwp'
        })
        df = df.loc[df['cwp'].str.contains('-PWPl', na=False)]
        df['cwp'] = df['cwp'].str.replace('-PWPl', '')
        df.loc[~df['cwp'].str.contains('-CWP'), 'cwp'] = df['cwp'] + '-CWP'
        return df



class FamMining():
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'fam mining' in item.lower():
                    workbook = pd.ExcelFile(os.path.join(source_dir, item))
                    for sheet_name in workbook.sheet_names:
                        if 'fam' in sheet_name.lower():
                            self.df_scheduler = workbook.parse(
                                sheet_name=sheet_name,
                                usecols=['Start', 'Finish', 'PWP (PWPe/PWP/PWPl)', 'Activity Name']
                            )
                            break

    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'Start': 'data_inicio', 
            'Finish': 'data_termino', 
            'PWP (PWPe/PWP/PWPl)': 'cwp',
            'Activity Name': 'descricao'
        })
        df = df.loc[df['cwp'].str.contains('-PWPl', na=False)]
        df = df.loc[df['descricao'].str.contains('Log??stica da CWA', na=False)]
        df['cwp'] = df['cwp'].str.replace('-PWPl', '')
        df.loc[~df['cwp'].str.contains('-CWP'), 'cwp'] = df['cwp'] + '-CWP'
        df = df.drop(columns=['descricao'])
        return df


class ModeloCronogramaCapanema():
    def __init__(self, file_name, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if file_name in item.lower():
                    self.df_scheduler = pd.read_excel(
                        os.path.join(source_dir, item),
                        usecols=['PWP', 'Nome da Tarefa', 'In??cio', 'T??rmino', 'In??cio da Linha de Base', 'T??rmino da Linha de Base']
                    )
                    break
    def get_report(self):
        return self.__class__._clean_report(self.df_scheduler)
    
    @staticmethod
    def _clean_report(df):
        df = df.rename(columns={
            'PWP': 'pwp', 
            'Nome da Tarefa': 'descricao', 
            'In??cio': 'data_inicio', 
            'T??rmino': 'data_termino',  
            'In??cio da Linha de Base': 'data_inicio_base',
            'T??rmino da Linha de Base': 'data_termino_base',
        })

        df['cwp'] = df['pwp'].str.replace('-PWP-', '-CWP-')
        return df


class RomaneioFAM():
    def __init__(self, source_dir) -> None:
        for item in os.listdir(source_dir):
            if os.path.isfile(os.path.join(source_dir, item)):
                if 'avan??o fabrica????o' in item.lower():
                    self.df_raw = pd.read_excel(
                        os.path.join(source_dir, item),
                        sheet_name='MEM??RIA',
                        skiprows=1,
                        usecols=['Cod Ajustada', 'Marca', 'Tipo Da Pe??a', 'Qtde. Total', 'Peso Unit. Strumis', 'Em Prepara????o', 'Preparado', 'Em Expedi????o', 'Qtde Expedida Obra']                  
                    )
                    break

    def get_report(self):
        self._clean_report()
        return self.df_report
    
    def _clean_report(self):
        df = self.df_raw
        df = df.rename(columns={
            'Cod Ajustada': 'cwp_short',
            'Marca': 'tag',
            'Tipo Da Pe??a': 'tipo',
            'Qtde. Total': 'qtd_total',
            'Peso Unit. Strumis': 'peso_un',
            'Em Prepara????o': 'peso_preparacao',
            'Preparado': 'peso_preparado',
            'Em Expedi????o': 'peso_expedicao',
            'Qtde Expedida Obra': 'qtd_entregue'
        })
        df = df.dropna(subset='tag')
        df = df.fillna(0)
        df['cwa'] = df['cwp_short'].str.replace('-', '').str.replace('CWP', 'CWA')
        df = df.loc[df['cwa'].str.contains('CWA')]
        df['chave'] = df['cwa'] + '-' + df['tag']

        df['qtd_embarque'] = (df['peso_expedicao']/ df['peso_un']) - df['qtd_entregue']
        df['qtd_embarque'] = df['qtd_embarque'].apply(lambda x: 0 if x < 0 else x)
        df['qtd_fabricacao'] = (df['peso_preparado'].astype(float) + df['peso_preparacao'] - df['peso_expedicao']) / df['peso_un']
        df['qtd_programacao'] = df['qtd_total'] - df['qtd_entregue'] - df['qtd_embarque'] - df['qtd_fabricacao'] 
        
        numeric_columns = ['qtd_entregue', 'qtd_fabricacao', 'qtd_embarque', 'qtd_programacao', 'qtd_total']
        categorical_columns = ['cwa', 'cwp_short', 'chave', 'tag', 'tipo', 'peso_un']

        df_numeric = df[numeric_columns + ['chave']].copy().groupby(by='chave', as_index=False).sum(numeric_only=True).round(0)
        df_categorical = df[categorical_columns].copy().drop_duplicates(subset='chave', keep='first')

        df = pd.merge(df_numeric, df_categorical, how='left', on='chave')

        df['total_sum'] = df[numeric_columns].sum(axis=1) - df['qtd_total']
        self.df_report = df