import { MapPin } from "lucide-react";

interface Recommendation {
  region: string;
  species: string[];
}

interface RecommendationsCardProps {
  recommendations: Recommendation[];
}

const RecommendationsCard = ({ recommendations }: RecommendationsCardProps) => {
  return (
    <div className="card-elevated p-5 bg-accent/50 border-primary/20">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
          <MapPin className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            Recomendações Inteligentes
          </h2>
          <p className="text-sm text-muted-foreground">
            Sugestões geradas a partir do déficit de arborização de cada RPA.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {recommendations.map((rec) => (
          <div key={rec.region} className="flex items-start gap-3">
            <span className="text-sm font-semibold text-foreground min-w-[80px]">
              {rec.region}
            </span>
            <div className="flex flex-wrap gap-2">
              {rec.species.map((species) => (
                <span
                  key={species}
                  className="px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20"
                >
                  {species}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RecommendationsCard;
