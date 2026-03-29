import CardItem from "./CardItem.jsx";

function CardGrid({ cards, imageMode }) {
  return (
    <div className="card-grid">
      {cards.map((card, index) => (
        <CardItem key={`${card.name}-${index}`} card={card} rank={index + 1} imageMode={imageMode} />
      ))}
    </div>
  );
}

export default CardGrid;
