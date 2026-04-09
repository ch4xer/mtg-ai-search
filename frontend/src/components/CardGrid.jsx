import CardItem from "./CardItem.jsx";

function CardGrid({ cards, imageMode, decks }) {
  return (
    <div className="card-grid">
      {cards.map((card, index) => (
        <CardItem key={`${card.name}-${index}`} card={card} imageMode={imageMode} decks={decks} />
      ))}
    </div>
  );
}

export default CardGrid;
