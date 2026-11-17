# PGO — Portal de Gestão Operacional

Portal web de gestão operacional para indústria. A aplicação atual possui login, seleção de setores e administração de usuários e permissões.

> Versão de portfólio: marca, imagens e dados são fictícios.

O layout possui ajustes dedicados para as resoluções corporativas `1366×768` e `1920×1080`, além dos breakpoints para tablets e celulares.

## Estrutura principal

```text
SGO/
├── index.html                 # Tela de login (rota /)
├── home/
│   └── index.html             # Seleção de setores (rota /home/)
├── administradores/
│   └── index.html             # Usuários e permissões (rota /administradores/)
├── setores/
│   └── index.html             # Home modular de cada setor (rota /setores/?setor=slug)
├── assets/
│   ├── css/
│   │   ├── login.css          # Estilos exclusivos do login
│   │   └── home.css           # Estilos exclusivos da home
│   ├── js/
│   │   ├── login.js           # Login pela API local
│   │   ├── administradores.js # CRUD de usuários e permissões
│   │   └── home.js            # Busca, perfil e encerramento da sessão
│   ├── images/
│   │   ├── branding/          # Logos e fundos institucionais
│   │   └── users/             # Fotos de usuários
│   ├── icons/                 # Ícones SVG próprios
│   └── vendor/                # Bibliotecas externas versionadas
├── scripts/
│   ├── build.mjs              # Gera a pasta dist/
│   └── dev.mjs                # Servidor de desenvolvimento Node.js
├── app.py                     # Servidor para a rede local na porta 5026
├── server/
│   ├── core/                  # Configuração, segurança, rotas e migrations
│   ├── migrations/            # Evolução versionada do banco
│   └── modules/               # Autenticação, auditoria e catálogo de setores
├── sgo_db.py                  # Camada de persistência legada em migração gradual
├── data/
│   └── sgo.db                 # Banco local gerado automaticamente
└── dist/                      # Saída gerada pelo build; não editar diretamente
```

## Como executar na rede local

```powershell
python app.py
```

O servidor usa a porta `5026` por padrão e exibe no terminal o endereço da máquina.
Na primeira execução ele cria `data/sgo.db`, cadastra os setores estruturais e a conta administrativa de teste.

## Como gerar o build

```powershell
npm run build
```

## Regras de manutenção

- Edite somente os arquivos-fonte; nunca altere arquivos dentro de `dist/`.
- Mantenha os dados administrativos na API/SQLite; não volte a fixar usuários no HTML ou JavaScript.
- Coloque logos e fundos em `assets/images/branding/`.
- Coloque fotos em `assets/images/users/` e ícones próprios em `assets/icons/`.
- Coloque bibliotecas de terceiros em `assets/vendor/`.
- Novas telas devem ficar em uma pasta de rota própria, contendo seu `index.html`.
- O arquivo `data/sgo.db` é local e ignorado pelo Git.

## Acesso de teste

- Usuário: `admin`
- Senha: `12345`

A senha é armazenada no SQLite com PBKDF2. A credencial inicial é exclusiva do ambiente de desenvolvimento e deve ser substituída antes de uma implantação real.

## Segurança e autorização

- O login cria uma sessão opaca armazenada no servidor e envia apenas um cookie `HttpOnly` e `SameSite=Strict` ao navegador.
- A área administrativa exige a permissão de perfil `administration.access` também no backend.
- Ativar a manutenção de um usuário revoga imediatamente todas as sessões dele.
- Setores e telas são lidos do banco; uma rota cadastrada só fica navegável quando também está registrada como implementada no código.

## Testes

```powershell
python -m unittest tests/test_foundation.py -v
npm run build
```

O workflow `.github/workflows/ci.yml` repete essas validações em cada push e pull request para `main`.

## Publicação no GitHub

O repositório oficial é `PedroBarboni/portal-gestao-operacional`. Para registrar e enviar um conjunto de alterações:

```powershell
.\scripts\publish.ps1 -Message "feat: descreva a alteração"
```

O script valida o remote, configura a identidade local quando necessário, cria o commit e envia a branch `main`.
