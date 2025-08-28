from contextlib import contextmanager
from typing import Iterator
import json

from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, status, Query, Body, Path, Form, Depends
from fastapi.responses import Response

from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import Column, Integer, String

from pydantic import BaseModel, EmailStr, Field

from typing import Optional, List

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

@contextmanager
def Database() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos Pydantic
class UsuarioBase(BaseModel):
    id: Optional[int] = None

class SetUser(UsuarioBase):
    nome: str
    email: EmailStr
    ativo: int = Field(default=1, description="1: ativo | 0: inativo")
    pass

    class Config:
        from_attributes = True

# # CRUD com SQLAlchemy
# class UsuarioCRUD:
#     @staticmethod
#     def criar(db: Session, usuario: SetUser):
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
#     def atualizar(db: Session, usuario_id: int, usuario: SetUser):
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
          response_model=SetUser,
          summary="Criar novo usuário",
          description="Cadastra um novo usuário no sistema.",
          responses={
              201: {"description": "Usuário criado com sucesso"},
              400: {"description": "Dados inválidos ou erro no banco de dados"}
          })
def criar_usuario(user_info: SetUser = Body(...)):
    try:
        new_user = UsuarioDB(**user_info.dict(exclude={"id"}))
        with Database() as banco:
            banco.add(new_user)
            banco.flush()
            banco.refresh(new_user)
            if new_user.id:
                 user_info.id = new_user.id
            banco.commit()
        return JSONResponse(json.loads(user_info.model_dump_json()), 201)
    except Exception as E:
        if isinstance(E, HTTPException):
            raise E
        else:
            raise HTTPException(400, str(E))

@app.get("/usuarios",
    response_model=List[SetUser],
    summary="Listar usuários",
    description="""Retorna todos os usuários cadastrados. 
                Pode ser filtrado por nome quando fornecido como parâmetro.""",
    responses={
        200: {"description": "Lista de usuários retornada com sucesso"},
        404: {"description": "Nenhum usuário encontrado"}
    })
def listar_usuarios(
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    ativo: Optional[int] = Query(default=-1, description="1: só ativos | 0: só inativos | -1: ativos e inativos"),
    nome: Optional[str] = Query(default="", description="Filtrar por nome"),
    ordenador: Optional[str] = Query(default="id", description="Ordernar por campos nome, id e ativo", )
):
    try:
        with Database() as banco:
            query = banco.query(UsuarioDB)

            if ativo is not None and ativo != -1:
                query = query.filter(UsuarioDB.ativo == ativo)
            elif ativo == -1:
                query = query.filter(UsuarioDB.ativo.in_([0, 1]))

            if id is not None:
                query = query.filter(UsuarioDB.id == id)

            if nome:
                query = query.filter(UsuarioDB.nome.ilike(f"%{nome.strip()}%"))

            colunas_permitidas = {
                "id": UsuarioDB.id,
                "nome": UsuarioDB.nome,
                "ativo": UsuarioDB.ativo
            }
            coluna_ordenacao = colunas_permitidas.get(ordenador, UsuarioDB.id)
            query = query.order_by(coluna_ordenacao.asc())

            db_users = query.all()

            if not db_users:
                raise HTTPException(status_code=404, detail="Nenhum usuário encontrado")
            
            return db_users
    except Exception as E:
        if isinstance(E, HTTPException):
            raise E
        else:
            raise HTTPException(400, str(E))

@app.patch("/usuarios",
         response_model=SetUser,
         summary="Atualizar usuário",
         description="Atualiza os dados de um usuário existente pelo seu ID.",
         responses={
             200: {"description": "Usuário atualizado com sucesso"},
             400: {"description": "Dados inválidos"},
             404: {"description": "Usuário não encontrado"}
         })
def atualizar_usuario(user_info: SetUser = Body(..., title="Dados do usuário para atualização")
):
    try:
        with Database() as banco:
            db_user = banco.query(UsuarioDB).filter(
                UsuarioDB.id == user_info.id
            ).update(
                user_info.model_dump(exclude_unset=True, exclude={"id"})
            )
            if db_user:
                banco.commit()
            else:
                raise HTTPException(404, 'Usuário já cadastrado')
        return JSONResponse(json.loads(user_info.model_dump_json()), 200)
    except Exception as E:
        if isinstance(E, HTTPException):
            raise E
        else:
            raise HTTPException(400, str(E))

@app.delete("/usuarios", 
            status_code=status.HTTP_204_NO_CONTENT,
            summary="Desativar usuário",
            description="Exclui logicamente um usuário do sistema pelo seu ID.",
            responses={
                204: {"description": "Usuário removido com sucesso"},
                404: {"description": "Usuário não encontrado"},
                500: {"description": "Erro interno no servidor"}
            })
def deletar_usuario(user_info: UsuarioBase = Body(..., title="Dados do usuário para atualização")):
    try:
        with Database() as banco:
            usuario = banco.query(UsuarioDB).filter(
                UsuarioDB.id == user_info.id
            ).update(
                {"ativo": 0}
            )
            if not usuario:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuário não encontrado"
                )
            banco.commit()
        return JSONResponse(json.loads(user_info.model_dump_json()), 200)
    except Exception as E:
        if isinstance(E, HTTPException):
            raise E
        else:
            raise HTTPException(400, str(E))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=5000,
        reload=True,
        workers=1
    )