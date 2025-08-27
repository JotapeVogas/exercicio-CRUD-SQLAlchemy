from fastapi import FastAPI, HTTPException, status, Query, Body, Path, Form, Depends
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo SQLAlchemy
class UsuarioDB(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    ativo = Column(Integer, nullable=False, default=1)

# Criar tabelas
Base.metadata.create_all(bind=engine)

# Dependência para obter sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos Pydantic
class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr
    ativo: int

class UsuarioCreate(UsuarioBase):
    pass

class Usuario(UsuarioBase):
    id: int

    class Config:
        from_attributes = True

# # CRUD com SQLAlchemy
# class UsuarioCRUD:
#     @staticmethod
#     def criar(db: Session, usuario: UsuarioCreate):
#         try:
#             db_usuario = UsuarioDB(**usuario.dict())
#             db.add(db_usuario)
#             db.commit()
#             db.refresh(db_usuario)
#             return db_usuario
#         except SQLAlchemyError as e:
#             db.rollback()
#             raise e

#     @staticmethod
#     def listar_com_filtro(
#         db: Session,
#         ativo: int | None = None,
#         nome: str | None = None,
#         ordenador: str | None = "id"
#     ):
#         query = db.query(UsuarioDB)
        
#         if ativo is not None and ativo != -1:
#             query = query.filter(UsuarioDB.ativo == ativo)
        
#         if nome:
#             query = query.filter(UsuarioDB.nome.ilike(f"%{nome}%"))
        
#         # Mapeamento seguro de ordenação
#         colunas_permitidas = {
#             "id": UsuarioDB.id,
#             "nome": UsuarioDB.nome,
#             "email": UsuarioDB.email
#         }
        
#         coluna_ordenacao = colunas_permitidas.get(ordenador, UsuarioDB.id)
#         query = query.order_by(coluna_ordenacao.asc())
        
#         return query.all()

#     @staticmethod
#     def atualizar(db: Session, usuario_id: int, usuario: UsuarioCreate):
#         try:
#             db_usuario = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first()
#             if not db_usuario:
#                 return None
            
#             for key, value in usuario.dict().items():
#                 setattr(db_usuario, key, value)
            
#             db.commit()
#             db.refresh(db_usuario)
#             return db_usuario
#         except SQLAlchemyError as e:
#             db.rollback()
#             raise e
    
#     @staticmethod
#     def buscar_por_id(db: Session, usuario_id: int):
#         return db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first()

#     @staticmethod
#     def deletar(db: Session, usuario_id: int):
#         try:
#             db_usuario = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first()
#             if db_usuario:
#                 db_usuario.ativo = 0
#                 db.commit()
#                 db.refresh(db_usuario)
#             return db_usuario
#         except SQLAlchemyError as e:
#             db.rollback()
#             raise e

# Rotas
@app.get("/", response_model=dict, 
         summary="Página inicial",
         description="Redireciona para a documentação interativa da API (Swagger UI).") 
def home():
    return {"escreva na URL": "http://127.0.0.1:8000/docs#/"}

@app.post("/usuarios", 
          status_code=status.HTTP_201_CREATED,
          response_model=Usuario,
          summary="Criar novo usuário",
          description="Cadastra um novo usuário no sistema.",
          responses={
              201: {"description": "Usuário criado com sucesso"},
              400: {"description": "Dados inválidos ou erro no banco de dados"}
          })
def criar_usuario(
    usuario: UsuarioCreate,
    db: Session = Depends(get_db)
):
    try:
        novo_usuario = UsuarioCRUD.criar(db, usuario)
        return novo_usuario
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao criar usuário: {str(e)}"
        )

@app.get("/usuarios",
    response_model=List[Usuario],
    summary="Listar usuários",
    description="""Retorna todos os usuários cadastrados. 
                Pode ser filtrado por nome quando fornecido como parâmetro.""",
    responses={
        200: {"description": "Lista de usuários retornada com sucesso"},
        404: {"description": "Nenhum usuário encontrado"}
    })
def listar_usuarios(
    ativo: Optional[int] = Query(default=None, description="1: só ativos | 0: só inativos | -1: ativos e inativos"),
    nome: Optional[str] = Query(default=None, description="Filtrar por nome"),
    ordenador: Optional[str] = Query(default="id", description="Ordernar por campos nome, id ou email"),
    db: Session = Depends(get_db)
):
    usuarios = UsuarioCRUD.listar_com_filtro(db, ativo, nome, ordenador)
    if not usuarios:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum usuário encontrado"
        )
    return usuarios

@app.patch("/usuarios/{usuario_id}",
         response_model=Usuario,
         summary="Atualizar usuário",
         description="Atualiza os dados de um usuário existente pelo seu ID.",
         responses={
             200: {"description": "Usuário atualizado com sucesso"},
             400: {"description": "Dados inválidos"},
             404: {"description": "Usuário não encontrado"}
         })
def atualizar_usuario(
    usuario_id: int = Path(..., title="ID do usuário"),
    usuario: UsuarioCreate = Body(..., title="Dados do usuário para atualização"),
    db: Session = Depends(get_db)
):
    try:
        usuario_existente = UsuarioCRUD.buscar_por_id(db, usuario_id)
        if not usuario_existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        usuario_atualizado = UsuarioCRUD.atualizar(db, usuario_id, usuario)
        
        if not usuario_atualizado:   
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao atualizar usuário no banco de dados"
            )
                   
        return usuario_atualizado
            
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar usuário: {str(e)}"
        )

@app.delete("/usuarios/{usuario_id}", 
            status_code=status.HTTP_204_NO_CONTENT,
            summary="Desativar usuário",
            description="Exclui logicamente um usuário do sistema pelo seu ID.",
            responses={
                204: {"description": "Usuário removido com sucesso"},
                404: {"description": "Usuário não encontrado"},
                500: {"description": "Erro interno no servidor"}
            })
def deletar_usuario(
    usuario_id: int = Path(..., title="ID do usuário", description="ID do usuário a ser removido"),
    db: Session = Depends(get_db)
):
    usuario = UsuarioCRUD.buscar_por_id(db, usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    UsuarioCRUD.deletar(db, usuario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=5000,
        reload=True,
        workers=1
    )