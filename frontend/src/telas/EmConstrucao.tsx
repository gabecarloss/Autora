type Props = { titulo: string; descricao: string };

export function EmConstrucao({ titulo, descricao }: Props) {
  return (
    <section>
      <h1>{titulo}</h1>
      <p className="explicacao">{descricao}</p>
      <p className="aviso">Em construção.</p>
    </section>
  );
}
